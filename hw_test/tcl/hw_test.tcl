# =============================================================================
# hw_test.tcl
# Hardware test for CRC-32/ISO-HDLC D=32 on Arty A7-100T via JTAG-AXI.
#
# Sends known packets through the AXI FIFO → CRC wrapper → AXI FIFO chain
# and checks each result against the software oracle.
#
# Usage (Vivado Tcl console, Hardware Manager open):
#   source hw_test/tcl/hw_test.tcl
# =============================================================================

# ── axi_fifo_mm_s register map (PG080 v4.x, base 0x44A00000, 32-bit width) ──
set FIFO_BASE 0x44A00000
set ISR  [expr {$FIFO_BASE + 0x000}]   ;# Interrupt Status Register
set IER  [expr {$FIFO_BASE + 0x004}]   ;# Interrupt Enable Register
set TDFR [expr {$FIFO_BASE + 0x008}]   ;# TX FIFO Reset        (write 0xA5)
set TDFV [expr {$FIFO_BASE + 0x00C}]   ;# TX FIFO Vacancy      (RO)
set TDFD [expr {$FIFO_BASE + 0x010}]   ;# TX FIFO Write Data
set TLR  [expr {$FIFO_BASE + 0x014}]   ;# Transmit Length      (triggers TX)
set RDFR [expr {$FIFO_BASE + 0x018}]   ;# RX FIFO Reset        (write 0xA5)
set RDFO [expr {$FIFO_BASE + 0x01C}]   ;# RX FIFO Occupancy    (RO)
set RDFD [expr {$FIFO_BASE + 0x020}]   ;# RX FIFO Read Data
set RLR  [expr {$FIFO_BASE + 0x024}]   ;# RX Length Register   (RO)
set SRR  [expr {$FIFO_BASE + 0x028}]   ;# Software Reset       (write 0xA0000000)

# ── Helper procedures ─────────────────────────────────────────────────────────
# Fixed transaction names + -force: no counter needed.
# get_hw_axi_txns returns the live object after create/run.

proc axil_write {addr data} {
    set txn [create_hw_axi_txn wr_txn [lindex [get_hw_axis] 0] \
        -type write -address [format %08X $addr] -data [format %08X $data] -force]
    run_hw_axi $txn
    delete_hw_axi_txn $txn
}

proc axil_read {addr} {
    set txn [create_hw_axi_txn rd_txn [lindex [get_hw_axis] 0] \
        -type read -address [format %08X $addr] -force]
    run_hw_axi $txn
    # DATA may be "DEADBEEF" or "0xDEADBEEF"; mask to 32 bits to keep unsigned
    scan [get_property DATA $txn] "%x" val
    delete_hw_axi_txn $txn
    return [expr {$val & 0xFFFFFFFF}]
}

proc fifo_reset {} {
    global SRR TDFR RDFR ISR
    axil_write $SRR  0xA0000000   ;# full software reset
    after 5
    axil_write $TDFR 0xA5         ;# TX FIFO reset
    axil_write $RDFR 0xA5         ;# RX FIFO reset
    after 5
    axil_write $ISR  0xFFFFFFFF   ;# clear all interrupt flags
}

# Write N 32-bit words to TDFD then assert TLAST via TLR.
proc send_packet {words} {
    global TDFD TLR
    foreach w $words { axil_write $TDFD $w }
    axil_write $TLR [expr {[llength $words] * 4}]
}

# Poll RDFO until occupancy > 0, drain all words, return the last.
# The AXI-S wrapper emits one beat per input beat; only the TLAST beat
# (the last word in the burst) carries the final XOR'd CRC result.
proc recv_crc {{timeout_ms 500}} {
    global RDFO RDFD
    set deadline [expr {[clock milliseconds] + $timeout_ms}]
    while {[clock milliseconds] < $deadline} {
        set occ [axil_read $RDFO]
        if {$occ > 0} {
            set result [axil_read $RDFD]
            for {set j 1} {$j < $occ} {incr j} {
                set result [axil_read $RDFD]
            }
            return $result
        }
        after 1
    }
    error "Timeout: RDFO stayed 0 for ${timeout_ms} ms"
}

# ── Program FPGA ──────────────────────────────────────────────────────────────
set script_dir [file dirname [file normalize [info script]]]
set bit_glob   [glob -nocomplain \
    [file join $script_dir ../vivado/crc_hw_test.runs/impl_1 \
               crc_test_wrapper.bit]]

if {[llength $bit_glob] == 0} {
    error "Bitstream not found. Run run_impl.tcl first."
}
set bitfile [lindex $bit_glob 0]

open_hw_manager
connect_hw_server -quiet
open_hw_target    -quiet

set dev [lindex [get_hw_devices] 0]
current_hw_device $dev
refresh_hw_device $dev

set_property PROGRAM.FILE $bitfile $dev
program_hw_devices $dev
puts "FPGA programmed: $bitfile"
refresh_hw_device $dev

set hw_axi [lindex [get_hw_axis] 0]
if {$hw_axi eq {}} { error "No hw_axi found — check bitstream includes jtag_axi_0." }
puts "JTAG-AXI: $hw_axi"

# ── Test vectors ──────────────────────────────────────────────────────────────
# Expected CRCs pre-computed by hw_test/sw/expected_crcs.py (crcZero oracle).
# Byte order: data_in[7:0] = first byte into LFSR.
#   hw word 0x34333231  ≡  b"\x31\x32\x33\x34"  =  "1234"
set test_vectors [list \
    "b'1234'     1-word"     {0x34333231}              0x9BE3E0A3 \
    "b'12345678' 2-word"     {0x34333231 0x38373635}   0x9AE0DAAF \
    "b'00000000' 1-word"     {0x00000000}              0x2144DF1C \
    "b'FFFFFFFF' 1-word"     {0xFFFFFFFF}              0xFFFFFFFF \
    "b'DEADBEEF' 1-word"     {0xEFBEADDE}              0x7C9CA35A \
    "b'AABBCCDD'*2 2-word"   {0xDDCCBBAA 0xDDCCBBAA}  0x1F6284EB \
]

# ── Run tests ─────────────────────────────────────────────────────────────────
fifo_reset

set pass 0
set fail 0
set total [expr {[llength $test_vectors] / 3}]

puts ""
puts "=== CRC-32/ISO-HDLC D=32 Hardware Test ==="
puts [format "  %-28s  %-12s  %-12s  %s" "Test" "Got" "Expected" "Result"]
puts [string repeat - 72]

for {set i 0} {$i < [llength $test_vectors]} {incr i 3} {
    set desc     [lindex $test_vectors $i]
    set words    [lindex $test_vectors [expr {$i+1}]]
    set expected [lindex $test_vectors [expr {$i+2}]]

    fifo_reset
    send_packet $words
    set got [recv_crc]

    if {$got == $expected} { set result PASS; incr pass } \
    else                   { set result "FAIL <<<"; incr fail }

    puts [format "  %-28s  0x%08X    0x%08X    %s" \
          $desc $got $expected $result]
}

puts [string repeat - 72]
if {$fail == 0} {
    puts "  ALL $total/$total TESTS PASSED"
} else {
    puts "  $pass PASSED  $fail FAILED  (of $total)"
}
puts ""
