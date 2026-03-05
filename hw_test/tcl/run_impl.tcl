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
puts "Launching synthesis..."
reset_run synth_1
launch_runs synth_1 -jobs [expr {min([exec nproc], 8)}]
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "Synthesis failed. Check Messages."
}
puts "Synthesis complete."

# ── Implementation + bitstream ────────────────────────────────────────────────
puts "Launching implementation + bitstream..."
launch_runs impl_1 -to_step write_bitstream -jobs [expr {min([exec nproc], 8)}]
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "Implementation failed. Check Messages."
}
puts "Implementation complete."

# ── Report bitstream location ─────────────────────────────────────────────────
set bit [glob [file join $script_dir ../vivado/crc_hw_test.runs/impl_1 \
              crc_test_wrapper.bit]]
puts ""
puts "Bitstream: $bit"
puts "Next: connect hardware and source hw_test/tcl/hw_test.tcl"
