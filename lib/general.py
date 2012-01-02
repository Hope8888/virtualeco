#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import time
import struct
import marshal
import traceback
import zipfile
import thread
import copy as py_copy
import ConfigParser
try: from cStringIO import StringIO
except: from StringIO import StringIO
from lib import db
from lib.site_packages import rijndael
DUMP_WITH_ZLIB = False
ZIP_MODE = "ZIP_STORED" #ZIP_DEFLATED, ZIP_STORED
STDOUT = sys.stdout
STDERR = sys.stderr
STDOUT_LOG = "./log/%s.log"
STDERR_LOG = "./log/%s_error.log"
ACCESORY_TYPE_LIST = ("ACCESORY_NECK",
				"JOINT_SYMBOL",
				)
UPPER_TYPE_LIST = ("ARMOR_UPPER",
				#"ONEPIECE",
				"COSTUME",
				"BODYSUIT",
				"WEDDING",
				"OVERALLS",
				"FACEBODYSUIT",
				)
LOWER_TYPE_LIST = ("ARMOR_LOWER",
				"SLACKS",
				)
RIGHT_TYPE_LIST = ("CLAW",
				"HAMMER",
				"STAFF",
				"SWORD",
				"AXE",
				"SPEAR",
				"HANDBAG",
				"GUN",
				"ETC_WEAPON",
				"SHORT_SWORD",
				"RAPIER",
				"BOOK",
				"DUALGUN",
				"RIFLE",
				"THROW",
				"ROPE",
				"BULLET",
				"ARROW",
				)
LEFT_TYPE_LIST = ("BOW",
				"SHIELD",
				"LEFT_HANDBAG",
				"ACCESORY_FINGER",
				"STRINGS",
				)
BOOTS_TYPE_LIST = ("LONGBOOTS",
				"BOOTS",
				"SHOES",
				"HALFBOOTS",
				)
PET_TYPE_LIST = ("BACK_DEMON",
				"PET",
				"RIDE_PET",
				"PET_NEKOMATA",
				)

class Log:
	def __init__(self, handle, base_path):
		self.handle = handle
		self.today = get_today()
		self.base_path = base_path
		self.logfile = open(base_path%self.today, "ab")
		self.logtime = True
	def write(self, s):
		try: self._write(s)
		except: self.handle.write("Log.write error: %s"%traceback.format_exc())
	def _write(self, s):
		self.handle.write(s)
		self.handle.flush()
		if self.logtime:
			if self.today != get_today():
				self.today = get_today()
				self.logfile.close()
				self.logfile = open(self.base_path%self.today, "ab")
			self.logfile.write(time.strftime("[%H:%M:%S]", time.localtime()))
			self.logfile.write(" ")
		self.logfile.write(s)
		self.logtime = False
		if s.endswith("\n"):
			self.flush()
			self.logtime = True
	def flush(self):
		try: self._flush()
		except: self.handle.write("Log.flush error: %s"%traceback.format_exc())
	def _flush(self):
		self.handle.flush()
		self.logfile.flush()
	def close(self):
		try: self._close()
		except: self.handle.write("Log.close error: %s"%traceback.format_exc())
	def _close(self):
		self.logfile.close()

def use_log():
	sys.stdout = Log(STDOUT, STDOUT_LOG)
	sys.stderr = Log(STDERR, STDERR_LOG)

def list_to_str(l):
	result = "".join(map(lambda item: "%s,"%item, l))
	return result.endswith(",") and result[:-1] or result
def str_to_list(string):
	return list(map(int, filter(None, string.split(","))))

def stringio(string):
	return StringIO(string)
def copy(obj):
	return py_copy.copy(obj)
def get_today():
	return time.strftime("%Y-%m-%d", time.localtime())

def get_item(item_id):
	item = db.item.get(item_id)
	if not item:
		item = db.item.get(10000000)
	return copy(item)
def get_pet(pet_id):
	pet = db.pet_obj.get(pet_id)
	if not pet:
		return
	return copy(pet)

def get_config_io(path):
	with open(path, "rb") as r:
		config = r.read()
	if config.startswith("\xef\xbb\xbf"):
		config = config[3:]
	return StringIO(config.replace("\r\n", "\n"))
def get_config(path=None):
	cfg = ConfigParser.SafeConfigParser()
	if path:
		cfg.readfp(get_config_io(path))
	return cfg

def load_dump(path):
	dump_path = "%s.dump"%path
	if not os.path.exists(dump_path):
		return
	modify_time = int(os.stat(path).st_mtime)
	python_ver = int("".join(map(str, sys.version_info[:3])))
	with open(dump_path, "rb") as dump:
		try:
			if (unpack_int(dump.read(4)) == modify_time and
				unpack_int(dump.read(4)) == python_ver):
				if DUMP_WITH_ZLIB:
					return marshal.loads(dump.read().decode("zlib"))
				else:
					return marshal.loads(dump.read())
		except:
			log_error("dump file %s broken."%dump_path, traceback.format_exc())
def save_dump(path, obj):
	dump_path = "%s.dump"%path
	modify_time = int(os.stat(path).st_mtime)
	python_ver = int("".join(map(str, sys.version_info[:3])))
	with open(dump_path, "wb") as dump:
		dump.write(pack_int(modify_time))
		dump.write(pack_int(python_ver))
		if DUMP_WITH_ZLIB:
			dump.write(marshal.dumps(obj).encode("zlib"))
		else	:
			dump.write(marshal.dumps(obj))

def save_zip(path_src, path_zip):
	zip_obj = zipfile.ZipFile(path_zip, "w", getattr(zipfile, ZIP_MODE))
	for root, dirs, files in os.walk(path_src):
		for dir_name in dirs:
			zip_obj.write(os.path.join(root, dir_name),
				os.path.join(root, dir_name).replace(path_src, ""))
		for file_name in files:
			zip_obj.write(os.path.join(root, file_name),
				os.path.join(root, file_name).replace(path_src, ""))
	zip_obj.close()

def log(*args):
	sys.stdout.write("".join(map(lambda s: str(s)+" ", args))[:-1]+"\n")
def log_line(*args):
	sys.stdout.write("".join(map(lambda s: str(s)+" ", args)))
def log_error(*args):
	sys.stderr.write("".join(map(lambda s: str(s)+" ", args))[:-1]+"\n")
def log_error_line(*args):
	sys.stderr.write("".join(map(lambda s: str(s)+" ", args)))

def pack_int(i):
	return struct.pack(">i", i)
def pack_short(i):
	return struct.pack(">h", i)
def pack_byte(i):
	return struct.pack(">b", i)
def unpack_int(s):
	return struct.unpack(">i", s)[0]
def unpack_short(s):
	return struct.unpack(">h", s)[0]
def unpack_byte(s):
	return struct.unpack(">b", s)[0]
def pack_unsigned_int(i):
	return struct.pack(">I", i)
def pack_unsigned_short(i):
	return struct.pack(">H", i)
def pack_unsigned_byte(i):
	return struct.pack(">B", i)
def unpack_unsigned_int(s):
	return struct.unpack(">I", s)[0]
def unpack_unsigned_short(s):
	return struct.unpack(">H", s)[0]
def unpack_unsigned_byte(s):
	return struct.unpack(">B", s)[0]
def pack_str(string):
	#65636f -> 04 65636f00
	if not string:
		return "\x01\x00"
	string += "\x00"
	return struct.pack(">B", len(string))+string #unsigned byte + char*
def unpack_str(code):
	string, length = unpack_raw(code)
	while string.endswith("\x00"):
		string = string[:-1]
	return string, length
def unpack_raw(code):
	length_data = code[:1]
	if length_data == "": return ""
	length = struct.unpack(">B", length_data)[0] #unsigned byte
	string = code[1:length+1]
	return string, length+1

def io_unpack_int(io):
	return struct.unpack(">i", io.read(4))[0]
def io_unpack_short(io):
	return struct.unpack(">h", io.read(2))[0]
def io_unpack_byte(io):
	return struct.unpack(">b", io.read(1))[0]
def io_unpack_unsigned_int(io):
	return struct.unpack(">I", io.read(4))[0]
def io_unpack_unsigned_short(io):
	return struct.unpack(">H", io.read(2))[0]
def io_unpack_unsigned_byte(io):
	return struct.unpack(">B", io.read(1))[0]
def io_unpack_str(io):
	string = io_unpack_raw(io)
	while string.endswith("\x00"):
		string = string[:-1]
	return string
def io_unpack_short_str(io):
	string = io_unpack_short_raw(io)
	while string.endswith("\x00"):
		string = string[:-1]
	return string
def io_unpack_raw(io):
	length_data = io.read(1)
	if length_data == "": return ""
	length = struct.unpack(">B", length_data)[0] #unsigned byte
	string = io.read(length)
	return string
def io_unpack_short_raw(io):
	length_data = io.read(2)
	if length_data == "": return ""
	length = struct.unpack(">H", length_data)[0] #unsigned short
	string = io.read(length)
	return string

def encode(string):
	if not string:
		log_error("encode error: not string", string)
		return
	key = "\x00"*16
	string_size = len(string)
	string += "\x00"*(16-len(string)%16)
	r = rijndael.rijndael(key, block_size=16)
	code = ""
	for i in xrange(len(string)/16):
		code += r.encrypt(string[i*16:i*16+16])
	code_size = len(code)
	return pack_int(code_size)+pack_int(string_size)+code

def decode(code):
	if not code:
		log_error("decode error: not code", code)
		return
	#00000010 0000000c 6677bcf44144b39e28281ae8777db574
	string_size = unpack_int(code[4:8])
	#code = code[8:]
	if (len(code)-8) % 16:
		log_error("decode error: (len(code)-8) % 16 != 0", code.encode("hex"))
		return
	key = "\x00"*16
	r = rijndael.rijndael(key, block_size=16)
	string = ""
	for i in xrange(len(code)/16):
		string += r.decrypt(code[i*16+8:i*16+24])
	return string[:string_size]
