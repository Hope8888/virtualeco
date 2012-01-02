#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import time
import thread
import threading
import traceback
from lib import db
from lib import users
from lib import general
SCRIPT_DIR = "./script"
script_list = {}
script_list_lock = threading.RLock()

def load():
	global server
	from lib import server
	with script_list_lock:
		_load()
def _load():
	general.log_line("Load", SCRIPT_DIR, "...")
	script_list.clear()
	for root, dirs, files in os.walk(SCRIPT_DIR):
		for name in files:
			path = os.path.join(root, name)
			if not path.endswith(".py"):
				continue
			#general.log("load script", path)
			obj = general.load_dump(path)
			try:
				if not obj:
					obj = compile(open(path, "rb").read(), path, "exec")
					general.save_dump(path, obj)
				namespace = {}
				exec obj in namespace
				script_id = namespace["ID"]
				if hasattr(script_id,"__iter__"):
					for i in script_id:
						script_list[i] = namespace
				else:
					script_list[script_id] = namespace
			except:
				general.log_error("script.load", path, traceback.format_exc())
	general.log("		%d	script	load."%len(script_list))

def run_script(pc, event_id):
	#general.log("run script id", event_id)
	with pc.lock and pc.user.lock:
		pc.event_id = event_id
		pc.user.map_client.send("05dc") #イベント開始の通知
		pc.user.map_client.send("05e8", event_id) #EventID通知 Event送信に対する応答
	with script_list_lock:
		event = script_list.get(event_id)
	try:
		if event:
			event["main"](pc)
		else:
			say(pc, "Script id %s not exist."%event_id, "")
			raise ValueError("Script id not exist")
	except:
		general.log_error("run_script", event_id, traceback.format_exc())
	with pc.lock and pc.user.lock:
		pc.event_id = 0
		if pc.online:
			pc.user.map_client.send("05dd") #イベント終了の通知

def run(pc, event_id):
	#if pc.event_id:
	#	general.log_error("script.run error: event duplicate", pc, pc.event_id)
	#	return
	thread.start_new_thread(run_script, (pc, event_id))

NAME_WITH_TYPE = {
	"run": (int,), #event_id
	"help": (),
	"reloadscript": (),
	"user": (),
	"say": (str, str, int, int), #message, npc_name, npc_motion_id, npc_id
	"msg": (str,), #message
	"servermsg": (str,), #message
	"where": (),
	"warp": (int, float, float), #map_id, x, y
	"warpraw": (int, int), #rawx, rawy
	"update": (),
	"hair": (int,), #hair_id
	"haircolor": (int,), #haircolor_id
	"face": (int,), #face_id
	"wig": (int,), #wig_id
	"ex": (int,), #ex_id
	"wing": (int,), #wing_id
	"wingcolor": (int,), #wingcolor_id
	"motion": (int, int), #motion_id, motion_loop
	"motion_loop": (int,), #motion_id
	"item": (int, int), #item_id, item_count
	"printitem": (),
	"takeitem": (int, int), #item_id, item_count
	"dustbox": (),
	"warehouse": (int,), #warehouse_id
	"playbgm": (int, int, int), #sound_id, loop, volume
	"playse": (int, int, int, int), #sound_id, loop, volume, balance
	"playjin": (int, int, int, int), #sound_id, loop, volume, balance
	"effect": (int, int, int, int, int), #effect_id, id, x, y, dir
	"speed": (int,), #speed
	"setgold": (int,), #gold
	"takegold": (int,), #gold_take
	"gold": (int,), #gold_give
	"npcmotion": (int, int, int), #npc_id, motion_id, motion_loop
	"npcmotion_loop": (int, int), #npc_id, motion_id
	"npcshop": (int,), #shop_id
	"npcsell": (),
	}

def help(pc):
	msg(pc, """
/run event_id
/help
/reloadscript
/user
/say message npc_name npc_motion_id npc_id
/msg message
/servermsg message
/where (~where)
/warp map_id x y
/warpraw rawx rawy
/update
/hair hair_id
/haircolor haircolor_id
/face face_id
/wig ex_id
/ex ex_id
/wing wing_id
/wingcolor wingcolor_id
/motion motion_id motion_loop
/motion_loop motion_id
/item item_id item_count
/printitem
/takeitem item_id item_count
/dustbox
/warehouse warehouse_id
/playbgm sound_id loop volume
/playse sound_id loop volume balance
/playjin sound_id loop volume balance
/effect effect_id id x y dir
/speed speed
/setgold gold
/takegold gold_take
/gold gold_give
/npcmotion npc_id motion_id motion_loop
/npcmotion_loop npc_id motion_id
/npcshop shop_id
/npcsell
""")

def handle_cmd(pc, cmd):
	if not (cmd.startswith("/") or cmd.startswith("~")):
		return
	l = filter(None, cmd[1:].split(" "))
	if not l:
		return
	name, args = l[0], l[1:]
	types = NAME_WITH_TYPE.get(name)
	if types == None:
		return
	try:
		request_gmlevel = server.config.gmlevel.get(name)
		if request_gmlevel == None:
			raise Exception("server.config.gmlevel[%s] not exist"%name)
		if pc.gmlevel < request_gmlevel:
			raise Exception("pc.gmlevel < request_gmlevel")
		try:
			for i, arg in enumerate(args):
				if not types[i]: continue
				args[i] = types[i](arg)
		except IndexError:
			pass
		eval(name)(pc, *args)
	except:
		exc_info = traceback.format_exc()
		msg(pc, filter(None, exc_info.split("\n"))[-1])
		general.log_error("script.handle_cmd [%s] error:\n"%cmd, exc_info)
	return True

def reloadscript(pc):
	servermsg(pc, "reloadscript...")
	load()
	servermsg(pc, "reloadscript success")

def user(pc):
	message = ""
	online_count = 0
	for p in users.get_pc_list():
		with p.lock:
			if not p.online:
				continue
			if not p.visible:
				continue
			message += "[%s] %s\n"%(p.map_obj.name, p.name)
			online_count += 1
	message += "online count: %d"%online_count
	msg(pc, message)

def say(pc, message, npc_name=None, npc_motion_id=131, npc_id=None):
	if npc_id == None:
		npc_id = pc.event_id
	if npc_name == None:
		npc = db.npc.get(pc.event_id)
		if npc: npc_name = npc.name
		else: npc_name = ""
	with pc.lock and pc.user.lock:
		pc.user.map_client.send("03f8") #NPCメッセージのヘッダー
		message = message.replace("$r", "$R").replace("$p", "$P")
		for message_line in message.split("$R"):
			pc.user.map_client.send("03f7", 
				message_line+"$R", npc_name, npc_motion_id, npc_id) #NPCメッセージ
		pc.user.map_client.send("03f9") #NPCメッセージのフッター

def msg(pc, message):
	with pc.lock and pc.user.lock:
		for line in message.replace("\r\n", "\n").split("\n"):
			pc.user.map_client.send("03e9", -1, line)

def servermsg(pc, message):
	with pc.lock and pc.user.lock:
		for line in message.replace("\r\n", "\n").split("\n"):
			pc.user.map_client.send_server("03e9", 0, line)

def where(pc):
	with pc.lock:
		msg(pc, "[%s] map_id: %s x: %s y: %s dir: %s rawx: %s rawy: %d rawdir: %s"%(
			pc.map_obj.name, pc.map_obj.map_id, pc.x, pc.y, pc.dir,
			pc.rawx, pc.rawy, pc.rawdir))

def warp(pc, map_id, x=None, y=None):
	if x != None and y != None:
		if x > 255 or x < 0: raise ValueError("x > 255 or < 0 [%d]"%x)
		if y > 255 or y < 0: raise ValueError("y > 255 or < 0 [%d]"%y)
	with pc.lock and pc.user.lock:
		if map_id != pc.map_obj.map_id:
			if not pc.set_map(map_id):
				raise ValueError("map_id %d not found."%map_id)
			if x != None and y != None: pc.set_coord(x, y)
			else: pc.set_coord(pc.map_obj.centerx, pc.map_obj.centery)
			pc.set_dir(0)
			pc.user.map_client.send_map_without_self("1211", pc) #PC消去
			pc.user.map_client.send("11fd", pc) #マップ変更通知
			pc.user.map_client.send("122a") #モンスターID通知
		else:
			if x != None and y != None: pc.set_coord(x, y)
			else: pc.set_coord(pc.map_obj.centerx, pc.map_obj.centery)
			pc.unset_pet()
			pc.user.map_client.send_map("11f9", pc, 14) #キャラ移動アナウンス #ワープ
			pc.set_pet()

def warpraw(pc, rawx, rawy):
	if rawx > 32767 or rawx < -32768:
		raise ValueError("rawx > 32767 or < -32768 [%d]"%rawx)
	if rawy > 32767 or rawy < -32768:
		raise ValueError("rawy > 32767 or < -32768 [%d]"%rawy)
	with pc.lock and pc.user.lock:
		pc.set_raw_coord(rawx, rawy)
		pc.unset_pet()
		pc.user.map_client.send_map("11f9", pc, 14) #キャラ移動アナウンス #ワープ
		pc.set_pet()

def update(pc):
	with pc.lock and pc.user.lock:
		pc.user.map_client.send_map("020e", pc) #キャラ情報

def hair(pc, hair_id):
	if hair_id > 32767 or hair_id < -32768:
		raise ValueError("hair_id > 32767 or < -32768 [%d]"%hair_id)
	with pc.lock:
		pc.hair = hair_id
	update(pc)

def haircolor(pc, haircolor_id):
	if haircolor_id > 127 or haircolor_id < -128:
		raise ValueError("haircolor_id > 127 or < -128 [%d]"%haircolor_id)
	with pc.lock:
		pc.haircolor = haircolor_id
	update(pc)

def face(pc, face_id):
	if face_id > 32767 or face_id < -32768:
		raise ValueError("face_id > 32767 or < -32768 [%d]"%face_id)
	with pc.lock:
		pc.face = face_id
	update(pc)

def wig(pc, wig_id):
	if wig_id > 32767 or wig_id < -32768:
		raise ValueError("wig_id > 32767 or < -32768 [%d]"%wig_id)
	with pc.lock:
		pc.wig = wig_id
	update(pc)

def ex(pc, ex_id):
	if ex_id > 127 or ex_id < -128:
		raise ValueError("ex_id > 127 or < -128 [%d]"%ex_id)
	with pc.lock:
		pc.ex = ex_id
	update(pc)

def wing(pc, wing_id):
	if wing_id > 127 or wing_id < -128:
		raise ValueError("wing_id > 127 or < -128 [%d]"%wing_id)
	with pc.lock:
		pc.ex = wing_id
	update(pc)

def wingcolor(pc, wingcolor_id):
	if wingcolor_id > 127 or wingcolor_id < -128:
		raise ValueError("wingcolor_id > 127 or < -128 [%d]"%wingcolor_id)
	with pc.lock:
		pc.wingcolor = wingcolor_id
	update(pc)

def motion(pc, motion_id, motion_loop=False):
	if motion_id > 32767 or motion_id < -32768:
		raise ValueError("motion_id > 32767 or < -32768 [%d]"%motion_id)
	pc.set_motion(motion_id, motion_loop)
	with pc.lock and pc.user.lock:
		pc.user.map_client.send_map("121c", pc) #モーション通知

def motion_loop(pc, motion_id):
	motion(pc, motion_id, True)

def item(pc, item_id, item_count=1):
	with pc.lock and pc.user.lock:
		return _item(pc, item_id, item_count)
def _item(pc, item_id, item_count):
	if item_count > 32767 or item_count < -32768:
		raise ValueError("item_count > 32767 or < -32768 [%d]"%item_count)
	if isinstance(item_id, long):
		raise ValueError("isinstance(item_id, long) [%d]"%item_id)
	while item_count:
		item = general.get_item(item_id)
		item_stock_exist = False
		if item.stock:
			for iid in pc.sort.item:
				item_exist = pc.item[iid]
				if item_exist.count >= 999:
					continue
				if item_exist.item_id != item_id:
					continue
				item_exist.count += item_count
				item_count = 0
				if item_exist.count > 999:
					item_count = item_exist.count-999
					item_exist.count = 999
				pc.user.map_client.send("09cf", item_exist, iid) #アイテム個数変化
				item_stock_exist = True
				break
		if item_stock_exist:
			continue
		if item_count > 999:
			item.count = 999
			item_count -= 999
		else:
			item.count = item_count
			item_count = 0
		item_iid = pc.get_new_iid()
		pc.item[item_iid] = item
		pc.sort.item.append(item_iid)
		pc.user.map_client.send("09d4", item, item_iid, 0x02) #アイテム取得 #0x02: body

def printitem(pc):
	with pc.lock:
		for iid in pc.sort.item:
			item = pc.item[iid]
			msg(pc, "%s iid: %d item_id: %d count: %d"%(
				item.name, iid, item.item_id, item.count))

def countitem(pc, item_id): #not for command
	if isinstance(item_id, long):
		raise ValueError("isinstance(item_id, long) [%d]"%item_id)
	item_count = 0
	with pc.lock and pc.user.lock:
		for iid, item in pc.item.iteritems():
			if pc.in_equip(iid):
				continue
			if item.item_id != item_id:
				continue
			item_count += item.count
	return item_count

def takeitem(pc, item_id, item_count=1):
	with pc.lock and pc.user.lock:
		return _takeitem(pc, item_id, item_count)
def _takeitem(pc, item_id, item_count):
	if item_count > 32767 or item_count < -32768:
		raise ValueError("item_count > 32767 or < -32768 [%d]"%item_count)
	if isinstance(item_id, long):
		raise ValueError("isinstance(item_id, long) [%d]"%item_id)
	if countitem(pc, item_id) < item_count:
		return False
	while item_count:
		for iid in pc.sort.item:
			if pc.in_equip(iid):
				continue
			item_exist = pc.item[iid]
			if item_exist.item_id != item_id:
				continue
			item_exist.count -= item_count
			#general.log(item_count, item_exist.count)
			item_count = 0
			if item_exist.count < 0:
				item_count = 0-item_exist.count
				item_exist.count = 0
			if item_exist.count > 0:
				pc.user.map_client.send("09cf", item_exist, iid) #アイテム個数変化
			else:
				pc.sort.item.remove(iid)
				pc.item.pop(iid)
				pc.user.map_client.send("09ce", iid) #インベントリからアイテム消去
			break
		else:
			return item_count
	return True

def dustbox(pc):
	run(pc, 12000170) #携帯ゴミ箱

def update_item(pc): #not for command
	with pc.lock and pc.user.lock:
		for iid, item in pc.item.iteritems():
			if pc.in_equip(iid):
				continue
			pc.user.map_client.send("09cf", item, iid) #アイテム個数変化

def npctrade(pc): #not for command
	pc.reset_trade()
	with pc.lock:
		pc.trade = True
		event_id = pc.event_id
	npc = db.npc.get(event_id)
	if npc: npc_name = npc.name
	else: npc_name = ""
	with pc.lock and pc.user.lock:
		pc.user.map_client.send("0a0f", npc_name, True) #トレードウィンドウ表示
	while True:
		with pc.lock:
			if not pc.online:
				return ()
			if not pc.trade:
				break
		time.sleep(0.1)
	update_item(pc)
	return pc.trade_return_list

def warehouse(pc, warehouse_id):
	if warehouse_id > 127 or warehouse_id < -128:
		raise ValueError("warehouse_id > 127 or < -128 [%d]"%warehouse_id)
	num_max = 300
	num_here = 0
	num_all = 0
	with pc.lock:
		for item in pc.warehouse.itervalues():
			num_all += 1
			if item.warehouse == warehouse_id:
				num_here += 1
	with pc.lock and pc.user.lock:
		#倉庫インベントリーヘッダ
		pc.user.map_client.send("09f6", warehouse_id, num_here, num_all, num_max)
		for iid, item in pc.warehouse.iteritems():
			if item.warehouse == warehouse_id:
				part = 30 #倉庫
			else:
				part = item.warehouse
			#倉庫インベントリーデータ
			pc.user.map_client.send("09f9", item, iid, part)
		pc.warehouse_open = warehouse_id
		pc.user.map_client.send("09fa") #倉庫インベントリーフッタ

def select(pc, option_list, title=""): #not for command
	option_list = filter(None, option_list)
	if len(option_list) > 65:
		raise ValueError("len(option_list) > 65")
	with pc.lock and pc.user.lock:
		pc.select_result = None
		#NPCのメッセージのうち、選択肢から選ぶもの
		pc.user.map_client.send("0604", option_list, title)
	while True:
		with pc.lock:
			if not pc.online:
				return
			if pc.select_result != None:
				return pc.select_result
		time.sleep(0.1)

def wait(pc, time_ms): #not for command
	if isinstance(time_ms, long):
		raise ValueError("isinstance(time_ms, long) [%d]"%time_ms)
	with pc.lock and pc.user.lock:
		pc.user.map_client.send("05eb", time_ms) #イベント関連のウェイト
	time.sleep(time_ms/1000.0)

def playbgm(pc, sound_id, loop=1, volume=100):
	if isinstance(sound_id, long):
		raise ValueError("isinstance(sound_id, long) [%d]"%sound_id)
	if volume > 100 or volume < 0:
		raise ValueError("volume > 100 or < 0 [%d]"%volume)
	with pc.lock and pc.user.lock:
		#音楽を再生する
		pc.user.map_client.send("05f0", sound_id, (loop and 1 or 0), volume)

def playse(pc, sound_id, loop=0, volume=100, balance=50):
	if isinstance(sound_id, long):
		raise ValueError("isinstance(sound_id, long) [%d]"%sound_id)
	if volume > 100 or volume < 0:
		raise ValueError("volume > 100 or < 0 [%d]"%volume)
	if balance > 100 or balance < 0:
		raise ValueError("balance > 100 or < 0 [%d]"%balance)
	with pc.lock and pc.user.lock:
		#効果音を再生する
		pc.user.map_client.send("05f5", sound_id, (loop and 1 or 0), volume, balance)

def playjin(pc, sound_id, loop=0, volume=100, balance=50):
	if isinstance(sound_id, long):
		raise ValueError("isinstance(sound_id, long) [%d]"%sound_id)
	if volume > 100 or volume < 0:
		raise ValueError("volume > 100 or < 0 [%d]"%volume)
	if balance > 100 or balance < 0:
		raise ValueError("balance > 100 or < 0 [%d]"%balance)
	with pc.lock and pc.user.lock:
		#ジングルを再生する
		pc.user.map_client.send("05fa", sound_id, (loop and 1 or 0), volume, balance)

def effect(pc, effect_id, id=None, x=None, y=None, dir=None):
	if isinstance(effect_id, long):
		raise ValueError("isinstance(effect_id, long) [%d]"%effect_id)
	if id != None and isinstance(id, long):
		raise ValueError("isinstance(id, long) [%d]"%id)
	if x != None and (x > 255 or x < 0):
		raise ValueError("x > 255 or < 0 [%d]"%x)
	if y != None and (y > 255 or y < 0):
		raise ValueError("y > 255 or < 0 [%d]"%y)
	if dir != None and (dir > 127 or dir < -128):
		raise ValueError("dir > 127 or < -128 [%d]"%dir)
	with pc.lock and pc.user.lock:
		#エフェクト受信
		pc.user.map_client.send_map("060e", pc, effect_id, id, x, y, dir)

def speed(pc, speed):
	if speed > 32767 or speed < -32768:
		raise ValueError("speed > 32767 or < -32768 [%d]"%speed)
	with pc.lock and pc.user.lock:
		pc.status.speed = speed
		pc.user.map_client.send_map("1239", pc) #キャラ速度通知・変更

def setgold(pc, gold):
	if isinstance(gold, long):
		raise ValueError("isinstance(gold, long) [%d]"%gold)
	with pc.lock and pc.user.lock:
		if gold < 0 or gold > 100000000:
			msg(pc, "setgold error: gold < 0 or gold > 100000000 [%s]"%gold)
			return False
		else:
			pc.gold = gold
			pc.user.map_client.send_map("09ec", pc) #ゴールドを更新する、値は更新後の値
			return True

def takegold(pc, gold_take):
	#general.log("takegold", gold_take)
	with pc.lock and pc.user.lock:
		return setgold(pc, pc.gold-gold_take)

def gold(pc, gold_give):
	#general.log("gold", gold_give)
	with pc.lock and pc.user.lock:
		return setgold(pc, pc.gold+gold_give)

def npcmotion(pc, npc_id, motion_id, motion_loop=False):
	if isinstance(npc_id, long):
		raise ValueError("isinstance(npc_id, long) [%d]"%npc_id)
	if motion_id > 32767 or motion_id < -32768:
		raise ValueError("motion_id > 32767 or < -32768 [%d]"%motion_id)
	with pc.lock and pc.user.lock:
		#モーション通知
		pc.user.map_client.send_map("121c", pc, npc_id, motion_id, motion_loop) 

def npcmotion_loop(pc, npc_id, motion_id):
	npcmotion(pc, npc_id, motion_id, True)

def npcshop(pc, shop_id):
	shop = db.shop.get(shop_id)
	if not shop:
		general.log_error("npc shop id %s not exist"%shop_id)
		return
	with pc.lock and pc.user.lock:
		pc.shop_open = shop_id
		pc.user.map_client.send_map("0613", pc, shop.item) #NPCのショップウィンドウ

def npcsell(pc):
	with pc.lock and pc.user.lock:
		pc.shop_open = 65535 #sell
		pc.user.map_client.send_map("0615") #NPCショップウィンドウ（売却）
