
import py.test
import os

from mech.fusion.bitstream.bitstream import BitStream
from mech.fusion.bitstream.formats import (Bit, Byte, ByteString,
                                           CString, Zero, UB,
                                           FloatFormat, FixedFormat)

def test_constructor():
    bits = BitStream("10")
    assert bits.bits == [True, False]

    bits = BitStream("10101100")
    assert bits.bits == [True, False, True, False, True, True, False, False]

    bits = BitStream("  1  ")
    assert len(bits) == 1

    bits = BitStream([True, False, True, False])
    assert str(bits) == "1010"

def test_read_bit():
    bits = BitStream("1001")
    assert bits.read(Bit) == 1
    assert bits.read(Bit) == 0
    assert bits.read(Bit) == 0
    assert bits.read(Bit) == 1
    assert bits.bits_available == 0
    py.test.raises(IndexError, bits.read, Bit)

def test_write_bit():
    bits = BitStream()
    bits.write(True)
    bits.write(False)
    bits.write(1, Bit)
    bits.write(0, Bit)
    assert str(bits) == "1010"
    assert bits.bits_available == 0

def test_cursor():
    bits = BitStream("01001101")
    assert bits.cursor == 0
    bits.seek(1, os.SEEK_END)
    assert bits.bits_available == 1
    assert bits.read(Bit) == 1
    py.test.raises(IndexError, bits.read, Bit)

    bits.rewind()
    assert bits.bits_available == 8

    result = bits.read(Bit)
    assert result == 0

    result = bits.read(BitStream[2])
    assert result == [True, False]

    bits.seek(1, os.SEEK_CUR)
    assert bits.bits_available == 4
    assert bits.read(BitStream[2]) == [True, True]

    bits.skip_to_end()
    assert bits.cursor == len(bits)

    bits.cursor = 0
    result = bits.read(BitStream[8])
    assert str(result) == str(bits)

def test_read_string():
    bits = BitStream("00101010")
    result = bits.read(ByteString[1])
    assert result == chr(42)
    assert bits.bits_available == 0

    bits = BitStream("00101010 00101111")
    result = bits.read(ByteString[2])
    assert result == chr(42) + chr(47)
    assert bits.bits_available == 0

    bits.rewind()
    result = bits.read(ByteString[2:"<"])
    assert result == chr(47) + chr(42)
    assert bits.bits_available == 0

    bits.rewind()
    test_data = "test 123\x01\xFF"
    bits.write(test_data, ByteString)
    bits.write(Zero[8])
    bits.rewind()
    result = bits.read(CString)
    assert result == test_data

    bits = BitStream()
    bits.write("adsfasfdgjklhrgokrjygaosaf", ByteString)
    bits.rewind()
    py.test.raises(ValueError, bits.read, CString)

def test_write_string():
    bits = BitStream()
    bits.write("FWS", ByteString)
    assert bits.bits_available == 0
    assert len(bits) == 24
    bits.rewind()
    result = bits.read(Byte)
    assert result == ord("F")
    result = bits.read(Byte)
    assert result == ord("W")
    result = bits.read(Byte)
    assert result == ord("S")
    assert bits.bits_available == 0

    bits = BitStream()
    bits.write("FWS", CString)
    assert bits.bits_available == 0
    assert len(bits) == 32
    bits.rewind()
    result = bits.read(Byte)
    assert result == ord("F")
    result = bits.read(Byte)
    assert result == ord("W")
    result = bits.read(Byte)
    assert result == ord("S")
    result = bits.read(Byte)
    assert result == 0
    assert bits.bits_available == 0

def test_read_bits():
    bits = BitStream("1011001")
    result = bits.read(4, BitStream[4])
    assert result == [True, False, True, True]
    assert bits.bits_available == 3
    py.test.raises(IndexError, bits.read, BitStream[4])

    bits = BitStream()
    bits.write("SWF", ByteString)
    
    bits.rewind()
    result = bits.read(BitStream[24:"<"])
    result = result.read(ByteString[3])
    assert result == "FWS"
    assert bits.bits_available == 0

def test_write_bits():
    L = [1, 0, True, False]
    
    bits = BitStream()
    bits.write(L)
    assert str(bits) == "1010"
    
    bits = BitStream("11")
    bits.write(L)
    assert str(bits) == "1010"

    bits = BitStream()
    bits.write(L[3:], BitStream[1])
    bits.write(L[2:], BitStream[1])
    assert str(bits) == "01"

    test = BitStream()
    test.write("SWF", ByteString)
    bits = BitStream()
    bits.write(test, BitStream["<"])
    
    bits.rewind()
    result = bits.read(ByteString[3])
    assert result == "FWS"
    assert bits.bits_available == 0

def test_read_int_value():
    bits = BitStream("101010")
    assert bits.read(UB[6]) == 42
    assert bits.bits_available == 9

    bits = BitStream("01011111111111")
    assert bits.read(UB[3]) == 2
    assert bits.read_int_value(11) == 2047

    bits = BitStream()
    bits.write("\xDD\xEE\xFF", ByteString)
    
    bits.rewind()
    result = bits.read(UB[24])
    assert result == 0xDDEEFF
    assert bits.bits_available == 0
    
    bits.rewind()
    result = bits.read(UB[24:"<"])
    assert result == 0xFFEEDD
    assert bits.bits_available == 0 

def test_write_int_value():
    bits = BitStream()
    bits.write(0b1111, UB[4])
    assert len(bits) == 4 and str(bits) == "1111"

    bits = BitStream()
    bits.write(0b1111, UB[8])
    assert len(bits) == 8 and str(bits) == "00001111"

    bits = BitStream()
    bits.write(0xDDEEFF, UB)
    bits.rewind()
    result = bits.read(ByteString[3])
    assert result == "\xDD\xEE\xFF"
    assert bits.bits_available == 0

    bits = BitStream()
    bits.write(0xDDEEFF, UB["<"])
    bits.rewind()
    result = bits.read(ByteString[3])
    assert result == "\xFF\xEE\xDD"
    assert bits.bits_available  == 0

def test_read_fixed_value():
    # TODO
    pass

def test_read_float_value_16():
    bits = BitStream("0100000000000000")
    result = bits.read(FloatFormat[16])
    assert result == 1
    assert bits.bits_available == 0
    
    bits = BitStream("0111110000000000")
    result = bits.read(FloatFormat[16])
    assert result == float("inf")
    assert bits.bits_available == 0
    
    bits = BitStream("1111110000000000")
    result = bits.read(FloatFormat[16])
    assert result == float("-inf")
    assert bits.bits_available == 0

def test_read_float_value_32():
    bits = BitStream("0 01111100 01000000000000000000000")
    result = bits.read(FloatFormat[32])
    assert result == 0.15625
    assert bits.bits_available == 0

    bits = BitStream("0 10000011 10010000000000000000000")
    result = bits.read(FloatFormat[32])
    assert result == 25
    assert bits.bits_available == 0

    bits = BitStream("0 11111111 00000000000000000000000")
    result = bits.read(FloatFormat[32])
    assert result == float("inf")
    assert bits.bits_available == 0

    bits = BitStream("1 11111111 00000000000000000000000")
    result = bits.read(FloatFormat[32])
    assert result == float("-inf")
    assert bits.bits_available == 0
    
def test_read_float_value_64():
    bits = BitStream("0011111111110000000000000000000000000000000000000000000000000000")
    result = bits.read(FloatFormat[64])
    assert result == 1
    assert bits.bits_available == 0
    
    bits = BitStream("0111111111110000000000000000000000000000000000000000000000000000")
    result = bits.read(FloatFormat[64])
    assert result == float("inf")
    assert bits.bits_available == 0

    bits = BitStream("1111111111110000000000000000000000000000000000000000000000000000")
    result = bits.read(FloatFormat[64])
    assert result == float("-inf")
    assert bits.bits_available == 0

def test_flush():
    bits = BitStream("11")
    bits.flush()
    assert str(bits) == "11000000"
    assert bits.bits_available == 0
    
    bits = BitStream("1111")
    bits.flush()
    assert str(bits) == "11110000"
    assert bits.bits_available == 0

    bits = BitStream("111111")
    bits.flush()
    assert str(bits) == "11111100"
    assert bits.bits_available == 0
    
    bits = BitStream("11111111")
    bits.flush()
    assert str(bits) == "11111111"
    assert bits.bits_available == 0
