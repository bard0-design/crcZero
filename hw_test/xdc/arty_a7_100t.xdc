## Arty A7-100T constraints for CRC hardware test
## Only clock and reset are needed — all data flows through JTAG-AXI.

## 100 MHz system clock (E3)
set_property -dict { PACKAGE_PIN E3  IOSTANDARD LVCMOS33 } [get_ports { sys_clk }]
create_clock -period 10.000 -name sys_clk -waveform {0.000 5.000} [get_ports { sys_clk }]

## CPU_RESETN pushbutton (C2, active-low)
set_property -dict { PACKAGE_PIN C2  IOSTANDARD LVCMOS33 } [get_ports { resetn }]
set_property PULLUP true [get_ports { resetn }]

## Heartbeat LED — LD0 (H5)
set_property -dict { PACKAGE_PIN H5  IOSTANDARD LVCMOS33 } [get_ports { led0 }]
