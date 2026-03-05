-- ==============================================================
-- crcZero -- AXI4-Stream CRC Wrapper (VHDL-1993)
-- https://github.com/bard0-design/crcZero
--
-- Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
-- License    : MIT
--
-- Algorithm  : CRC-32/ISO-HDLC
-- Wrapper    : crc_32_iso_hdlc_d8_axis
-- CRC core   : crc_32_iso_hdlc_d8
-- Data width : 8 bits
-- Generated  : 2026-03-06T06:17:39Z
--
-- Analyse both files together:
--   ghdl -a --std=93 crc_32_iso_hdlc_d8.vhd crc_32_iso_hdlc_d8_axis.vhd
-- ==============================================================

library ieee;
use ieee.std_logic_1164.all;

entity crc_32_iso_hdlc_d8_axis is
  port (
    clk           : in  std_logic;
    rst_n         : in  std_logic;  -- active-low synchronous reset
    -- AXI4-Stream slave (data in)
    s_axis_tdata  : in  std_logic_vector(7 downto 0);
    s_axis_tvalid : in  std_logic;
    s_axis_tready : out std_logic;
    s_axis_tlast  : in  std_logic;
    -- AXI4-Stream master (running CRC out, one beat per input beat)
    m_axis_tdata  : out std_logic_vector(31 downto 0);
    m_axis_tvalid : out std_logic;
    m_axis_tlast  : out std_logic;
    m_axis_tready : in  std_logic
  );
end crc_32_iso_hdlc_d8_axis;

architecture rtl of crc_32_iso_hdlc_d8_axis is

  constant HW_INIT : std_logic_vector(31 downto 0) := x"FFFFFFFF";
  constant XOR_OUT : std_logic_vector(31 downto 0) := x"FFFFFFFF";

  signal crc_reg    : std_logic_vector(31 downto 0) := HW_INIT;
  signal crc_next   : std_logic_vector(31 downto 0);
  signal m_tdata_r  : std_logic_vector(31 downto 0) := (others => '0');
  signal m_tvalid_r : std_logic := '0';
  signal m_tlast_r  : std_logic := '0';
  -- Internal readable copy of s_axis_tready (VHDL-2008: out ports are not readable)
  signal s_tready_i : std_logic;

begin

  -- Combinatorial CRC core (generated separately)
  u_crc_core : entity work.crc_32_iso_hdlc_d8(rtl)
    port map (
      data_in => s_axis_tdata,
      crc_in  => crc_reg,
      crc_out => crc_next
    );

  -- s_tready: pipeline stage ready when output is free or downstream consuming
  s_tready_i    <= '1' when m_tvalid_r = '0' or m_axis_tready = '1' else '0';
  s_axis_tready <= s_tready_i;
  m_axis_tlast  <= m_tlast_r;
  m_axis_tdata  <= m_tdata_r;
  m_axis_tvalid <= m_tvalid_r;

  reg_p : process(clk)
  begin
    if rising_edge(clk) then
      if rst_n = '0' then
        crc_reg    <= HW_INIT;
        m_tvalid_r <= '0';
        m_tlast_r  <= '0';
        m_tdata_r  <= (others => '0');
      else
        if s_tready_i = '1' then
          if s_axis_tvalid = '1' then
            m_tvalid_r <= '1';
            m_tlast_r  <= s_axis_tlast;
            if s_axis_tlast = '1' then
              m_tdata_r <= crc_next xor XOR_OUT;
              crc_reg   <= HW_INIT;
            else
              m_tdata_r <= crc_next;
              crc_reg   <= crc_next;
            end if;
          else
            m_tvalid_r <= '0';
            m_tlast_r  <= '0';
          end if;
        end if;
      end if;
    end if;
  end process;

end rtl;
