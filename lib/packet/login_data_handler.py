#!/usr/bin/env python
# -*- coding: utf-8 -*-
import traceback
import hashlib
import os
from lib import general
from lib.packet import packet
from lib import users
WORD_FRONT = "0000"
WORD_BACK = "0000"
DATA_TYPE_NOT_PRINT = (	"000a", #接続確認
					)

class LoginDataHandler:
	def __init__(self):
		self.user = None
		self.pc = None
	
	def send(self, *args):
		self.send_packet(packet.make(*args))
	
	def stop(self):
		if self.user:
			self.user.reset_login()
			self.user = None
		self._stop()
	
	def handle_data(self, data_decode):
		#000a 0001 000003f91e07e221
		while data_decode:
			data_length = general.unpack_short(data_decode[:2])
			data_type = data_decode[2:4].encode("hex")
			data = data_decode[4:data_length+2]
			data_decode = data_decode[data_length+2:]
			if data_type not in DATA_TYPE_NOT_PRINT:
				general.log("[login] %s %s %s"%(
					general.pack_short(data_length).encode("hex"),
					data_type,
					data.encode("hex")))
			try:
				handler = getattr(self, "do_%s"%data_type)
			except AttributeError:
				general.log_error("[login] unknow packet type",
					data_type, data.encode("hex"))
				return
			try:
				handler(data)
			except:
				general.log_error("[login] handle_data error:", data.encode("hex"))
				general.log_error(traceback.format_exc())
	
	def do_0001(self, data):
		general.log("[login] eco version", general.unpack_int(data[:4]))
		self.send("0002", data) #認証接続確認(s0001)の応答
		self.send("001e", WORD_FRONT+WORD_BACK) #PASS鍵
	
	def do_001f(self, data):
		general.log_line("[login]", "login")
		username, username_length = general.unpack_str(data)
		password_sha1 = general.unpack_str(data[username_length:])[0]
		general.log(username, password_sha1)
		for user in users.get_user_list():
			with user.lock:
				if user.name != username:
					continue
				user_password_sha1 = hashlib.sha1(
					"".join((str(general.unpack_int(WORD_FRONT)),
							user.password,
							str(general.unpack_int(WORD_BACK)),
							))).hexdigest()
				if user_password_sha1 != password_sha1:
					self.send("0020", user, "loginfaild") #アカウント認証結果
					return
				if user.login_client:
					user.reset_login()
					self.send("0020", user, "isonline") #アカウント認証結果
					return
				user.reset_login()
				user.login_client = self
				self.user = user
				self.send("0020", user, "loginsucess") #アカウント認証結果
				self.send("0028", user) #4キャラクターの基本属性
				self.send("0029", user) #4キャラクターの装備
				break
		else:
			self.send("0020", user, "loginfaild") #アカウント認証結果
	
	def do_000a(self, data):
		#接続確認
		self.send("000b", data) #接続・接続確認(s000a)の応答

	def do_00a0(self, data):
		#キャラクター作成
		#02 03313100 00 00 0000 32 0000
		num = general.unpack_byte(data[:1]); data = data[1:]
		name, length = general.unpack_str(data); data = data[length:]
		race = general.unpack_byte(data[:1]); data = data[1:]
		gender = general.unpack_byte(data[:1]); data = data[1:]
		hair = general.unpack_short(data[:2]); data = data[2:]
		hair_color = general.unpack_byte(data[:1]); data = data[1:]
		face = general.unpack_short(data[:2]); data = data[2:]
		general.log("[login] new character:", "num", num, "name", name,
			"race", race, "gender", gender, "hair", hair,
			"haircolor", hair_color, "face", face)
		try:
			if self.user.pc_list[num]:
				self.send("00a1", "slotexist") #キャラクター作成結果
				return
			if users.get_pc_from_name(name):
				self.send("00a1", "nameexist") #キャラクター作成結果
				return
			if hair > 15 or hair_color < 50:
				raise ValueError(
					"user %s hair %s hair_color %s"%(
					self.user.name, hair, hair_color))
				return
			if not users.make_new_pc(
				self.user, num, name, race, gender, hair, hair_color, face):
				self.send("00a1", "slotexist") #キャラクター作成結果
				return
		except:
			general.log_error("do_00a0 error:", data.encode("hex"))
			general.log_error(traceback.format_exc())
			self.send("00a1", "other") #キャラクター作成結果
			return
		else:
			self.send("00a1", "sucess") #キャラクター作成結果
			self.send("0028", self.user) #4キャラクターの基本属性
			self.send("0029", self.user) #4キャラクターの装備
	
	def do_00a5(self, data):
		#キャラクター削除 #num + delpassword
		num = general.unpack_byte(data[:1]); data = data[1:]
		delpassword_md5, length = general.unpack_str(data); data = data[length:]
		general.log("[login] delete character", "num", num,
			"delpassword", delpassword_md5)
		try:
			if self.user.delpassword != delpassword_md5:
				raise (Exception, "delpassword error")
			with self.user.lock:
				os.remove(self.user.pc_list[num].path)
				self.user.pc_list[num] = None
			self.send("00a6", True) #キャラクター削除結果
		except:
			general.log_error("do_00a5 error:", traceback.format_exc())
			self.send("00a6", False) #キャラクター削除結果
		self.send("0028", self.user) #4キャラクターの基本属性
		self.send("0029", self.user) #4キャラクターの装備
	
	def do_00a7(self, data):
		num = general.unpack_byte(data[:1])
		general.log("[login] select character", num)
		with self.user.lock:
			self.pc = self.user.pc_list[num]
		self.send("00a8", self.pc) #キャラクターマップ通知
	
	def do_0032(self, data):
		mapid = general.unpack_int(data[:4])
		self.send("0033") #接続先通知要求(ログインサーバ/0032)の応答
	
	def do_002a(self, data):
		general.log("[login]", "request friend list")
		if self.pc:
			self.send("00dd", self.pc) #フレンドリスト(自キャラ)
