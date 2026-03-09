# =============================================================================
# run_impl.tcl
# Runs synthesis, implementation, and bitstream generation.
#
# Usage (from Vivado Tcl console, after create_project.tcl):
#   source hw_test/tcl/run_impl.tcl
# =============================================================================

set script_dir [file dirname [file normalize [info script]]]

# Open the project if not already open
if {[catch {current_project}]} {
    set xpr [glob -nocomplain [file join $script_dir ../vivado/*.xpr]]
    if {$xpr eq {}} { error "No .xpr found. Run create_project.tcl first." }
    open_project [lindex $xpr 0]
}

# ── Synthesis ─────────────────────────────────────────────────────────────────
# Detect CPU count cross-platform (nproc on Linux/macOS, NUMBER_OF_PROCESSORS on Windows)
if {[catch {set ncpu [exec nproc]}]} {
    if {[info exists ::env(NUMBER_OF_PROCESSORS)]} {
        set ncpu $::env(NUMBER_OF_PROCESSORS)
    } else {
        set ncpu 4   ;# safe fallback
    }
}
set njobs [expr {min($ncpu, 8)}]

puts "Launching synthesis..."
reset_run synth_1
launch_runs synth_1 -jobs $njobs
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "Synthesis failed. Check Messages."
}
puts "Synthesis complete."

# ── Implementation + bitstream ────────────────────────────────────────────────
puts "Launching implementation + bitstream..."
launch_runs impl_1 -to_step write_bitstream -jobs $njobs
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "Implementation failed. Check Messages."
}
puts "Implementation complete."

# ── Timing closure check ────────────────────────────────────────────────────
open_run impl_1
set wns [get_property SLACK [get_timing_paths -max_paths 1 -setup]]
set whs [get_property SLACK [get_timing_paths -max_paths 1 -hold]]
puts ""
puts "Timing: WNS = ${wns} ns, WHS = ${whs} ns"
if {$wns < 0} {
    puts "WARNING: Setup timing violated (WNS = ${wns} ns). Bitstream may not work reliably."
    puts "         Consider relaxing clock constraints or optimizing placement."
}
if {$whs < 0} {
    puts "WARNING: Hold timing violated (WHS = ${whs} ns). Bitstream may not work reliably."
}
if {$wns >= 0 && $whs >= 0} {
    puts "Timing closure: PASS"
}

# ── Report bitstream location ─────────────────────────────────────────────────
set bit [glob [file join $script_dir ../vivado/crc_hw_test.runs/impl_1 \
              crc_test_wrapper.bit]]
puts ""
puts "Bitstream: $bit"
puts "Next: connect hardware and source hw_test/tcl/hw_test.tcl"
