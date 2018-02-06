
# coding: utf-8
import numpy as np
import pandas as pd
import json, sqlite3, codecs
from llatb.common.global_var import gem_skill_id_dict, muse, Aqours
from llatb.common.config import card_archive_dir, unit_db_dir
from llatb.framework.card import Card, card_dataframe
from llatb.framework.team import Team
from llatb.importer.formatter import *

# Load basic stats from data_base.json
raw_card_dict = {k:Card.fromJSON(v) for k,v in json.loads(open(card_archive_dir).read()).items()}
try:
	raw_card_dict = {k:Card.fromJSON(v) for k,v in json.loads(open(card_archive_dir).read()).items()}
except:
	print('Data base json file {0} does not exist!'.format(card_archive_dir))
# Load uid cid correspondence from unit.db
try:
	uid_cid_dict = {str(k):str(v) for k,v in sqlite3.connect(unit_db_dir).cursor().execute("SELECT unit_id, unit_number FROM unit_m").fetchall()}
	for i, x in enumerate(range(1243,1252),1): uid_cid_dict[str(x)] = str(2000+i)
	cid_uid_dict = {v:k for k,v in uid_cid_dict.items()}
except:
	print('Please update the data base')

class GameData:
	def __init__(self, filename=None, file_type='packet', string_input=False):
		def gen_card(c, equip=True):
			card = raw_card_dict[c['card_id']].copy()
			card.idolize(c['idolized'])
			card.level_up(*[c[attr] for attr in ['skill_level', 'slot_num', 'level', 'bond']])
			if equip: card.equip_gem(c['equipped_gems'])
			return card
		if filename is None:
			self.raw_card = raw_card_dict
			self.owned_card = card_dataframe(raw_card_dict)
			self.owned_gem = {k:0 for k in list(gem_skill_id_dict.values())}
			self.team_list = []
		else:
			try:
				if file_type == 'packet':
					card_info, gem_owning_info, deck_info = self.get_user_packet_info(filename)
				elif file_type == 'ieb':
					card_info, gem_owning_info, deck_info = self.get_ieb_info(filename, string_input)
				elif file_type == 'pll':
					card_info, gem_owning_info, deck_info = self.get_pll_info(filename, string_input)
				elif file_type == 'minaraishi':
					card_info, gem_owning_info, deck_info = self.get_minaraishi_info(filename, string_input)
				elif file_type == 'SIT':
					card_info, gem_owning_info, deck_info = self.get_SIT_info(filename, string_input)
				else:
					print('Incorrect file type {0}. Please choose packet or ieb'.format(file_type))
					raise
				# Owned skill gems of user
				self.owned_gem = {k:0 for k in list(gem_skill_id_dict.values())}
				self.owned_gem.update(gem_owning_info)
				# Owned cards of user: dict of gem-unequipped cards
				self.raw_card = { k:gen_card(c, equip=False) for k,c in card_info.items() if c['card_id'] != '0'}
				self.owned_card = card_dataframe(self.raw_card)
				# Teams of user: list of gem-equipped cards
				self.team_list = [ None if deck is None else Team([gen_card(c,equip=True) for c in deck]) for deck in deck_info ]
			except:
				print('Failed to generate user information from profile file{0}!'.format(' ' + filename if not string_input else ''))
	def get_user_packet_info(self, packet_file):
		def load_packets(packet_file):
			def fix_file(file_name):
				text = open(file_name).read()
				lines, last = text.split('\n'), None
				if lines[-1] != ']':
					# When the packet file is broken, drop the last incomplete packet
					for i, line in enumerate(reversed(lines)):
						if '},' == line.strip():
							indent, last = len(line)-len(line.lstrip())-2, len(lines) - i - 1
							lines[last] = line.replace(',','')
							break
					if last is not None:
						lines = lines[:last+1] + [' '*i+'}' for i in range(indent,0,-2)] + ['', ']']
					text = '\n'.join(lines)
				return text
			def extract_json(packet):
				if packet['_source']['layers'].get('http') is None or packet['_source']['layers']['http'].get("http.file_data") is None: return None
				text = packet['_source']['layers']['http']['http.file_data']
				text = text[text.find('{'):text.rfind('}')+1]
				try:
					return eval(text.replace('true','True').replace('false','False').replace('null','None'))
				except:
					return None
			packets = json.loads(fix_file(packet_file))
			is_response_data = lambda item: False if item is None else (type(item)==dict and item.get('response_data') is not None)
			responses = [x for x in [extract_json(packet) for packet in packets] if is_response_data(x)]
			for resp in responses:
				resp_data = resp['response_data']
				if type(resp_data) == list and len(resp_data) > 0 and len(resp_data) >= 10:
					useful_info = resp_data
			result, profile = dict(), dict()
			for item in useful_info:
				temp = item['result']
				if temp == []:
					continue
				elif type(temp) == dict and temp.get('equipment_info') is not None:
					result['gem_equip_info'] = temp['equipment_info']
					result['gem_owning_info'] = temp['owning_info']
					profile['removable_info'] = temp
				elif type(temp) == list:
					if temp[0].get('display_rank') is not None:
						result['card_owning_info'] = temp
						profile['unit_info'] = temp
					elif temp[0].get('deck_name') is not None:
						result['deck_info'] = temp
						profile['deck_info'] = temp
			with open('packet_to_json.json', 'w') as fp:
				fp.write(json.dumps(profile))
			return result
		def get_card_levelup_info(card_info):
			res = {
				'unit_id':str(card_info['unit_id']),
				'card_id':uid_cid_dict[str(card_info['unit_id'])],
				'idolized':card_info['rank'] == 2,
				'level':card_info['level'],
				'bond':card_info['love'],
				'skill_level':card_info['unit_skill_level'],
				'slot_num':card_info['unit_removable_skill_capacity'],
				'equipped_gems':[]
			}
			return res
		# Load packet file
		temp = load_packets(packet_file)
		# Generate user card information
		card_info, owning_id_dict = dict(), dict()
		for i, card in enumerate(temp['card_owning_info'], 1):
			try:
				card_info[str(i)] = get_card_levelup_info(card)
				owning_id_dict[str(card['unit_owning_user_id'])] = str(i)
			except:
				print('{0} is not in uid_cid_dict, please update {1}'.format(card['unit_id'], self.unit_db_file))
		for key, value in temp['gem_equip_info'].items():
			card_info[owning_id_dict[key]]['equipped_gems'] = [gem_skill_id_dict[x['unit_removable_skill_id']] for x in value['detail']]
		# Generate user gem information
		gem_owning_info = { skill_name:0 for skill_name in list(gem_skill_id_dict.values()) }
		for x in temp['gem_owning_info']:
			skill_name = gem_skill_id_dict[x['unit_removable_skill_id']]
			gem_owning_info[skill_name] = x['total_amount']
		# Generate user team information
		deck_info = []
		for deck in temp['deck_info']:
			ids = [card_info[owning_id_dict[str(x['unit_owning_user_id'])]] for x in deck['unit_owning_user_ids']]
			deck_info.append(ids)
		return card_info, gem_owning_info, deck_info
	def get_ieb_info(self, ieb_file, string_input=False):
		def get_card_levelup_info(card_info):
			res = {
				'unit_id':str(card_info['unit_id']),
				'card_id':uid_cid_dict[str(card_info['unit_id'])],
				'idolized':card_info['rank'] == 2,
				'level':card_info['level'],
				'bond':card_info['love'],
				'skill_level':card_info['unit_skill_level'],
				'slot_num':card_info['unit_removable_skill_capacity'],
				'equipped_gems':[]
			}
			return res
		ieb_info = json.loads(ieb_file if string_input else open(ieb_file).read())
		# Generate user card information
		card_info, owning_id_dict = dict(), dict()
		error_capture = ''
		for i, card in enumerate(ieb_info['unit_info'], 1):
			try:
				card_info[str(i)] = get_card_levelup_info(card)
				owning_id_dict[str(card['unit_owning_user_id'])] = str(i)
			except:
				if error_capture == '': error_capture += ieb_file
				print('{0} is not in uid_cid_dict, please update {1}'.format(card['unit_id'], unit_db_dir))
		# if error_capture != '': print(error_capture)
		for key, value in ieb_info['removable_info']['equipment_info'].items():
			card_info[owning_id_dict[key]]['equipped_gems'] = [gem_skill_id_dict[x] for x in value]
		# Generate user gem information
		gem_owning_info = { skill_name:0 for skill_name in list(gem_skill_id_dict.values()) }
		for x in ieb_info['removable_info']['owning_info']:
			skill_name = gem_skill_id_dict[x['unit_removable_skill_id']]
			gem_owning_info[skill_name] = x['total_amount']
		# Generate user team information
		deck_info = []
		for i, deck in enumerate(ieb_info['deck_info'],1):
			ids = [card_info[owning_id_dict[str(x['unit_owning_user_id'])]] for x in deck['unit_owning_user_ids']]
			if len(ids) == 9:
				deck_info.append(ids)
			else:
				print('Invalid team: {0}-th team only has {1} members placed'.format(i, len(ids)))
				deck_info.append(None)
		return card_info, gem_owning_info, deck_info
	def get_pll_info(self, pll_file, string_input=False):
		def get_card_levelup_info(card_info):
			res = {
				'unit_id':str(card_info['unit_id']),
				'card_id':uid_cid_dict[str(card_info['unit_id'])],
				'idolized':card_info['rank'] == 2,
				'level':card_info['level'],
				'bond':card_info['love'],
				'skill_level':card_info['unit_skill_level'],
				'slot_num':card_info['unit_removable_skill_capacity'],
				'equipped_gems':[]
			}
			return res
		pll_info = json.loads(pll_file if string_input else open(pll_file).read())
		# Generate user card information
		card_info, owning_id_dict = dict(), dict()
		error_capture = ''
		for i, card in enumerate(pll_info['unit_info'], 1):
			try:
				card_info[str(i)] = get_card_levelup_info(card)
				owning_id_dict[str(card['unit_owning_user_id'])] = str(i)
			except:
				if error_capture == '': error_capture += pll_file
				print('{0} is not in uid_cid_dict, please update {1}'.format(card['unit_id'], unit_db_dir))
		# if error_capture != '': print(error_capture)
		for key, equip_info in pll_info['removable_info']['equipment_info'].items():
			value = [x['unit_removable_skill_id'] for x in equip_info['detail']]
			card_info[owning_id_dict[key]]['equipped_gems'] = [gem_skill_id_dict[x] for x in value]
		# Generate user gem information
		gem_owning_info = { skill_name:0 for skill_name in list(gem_skill_id_dict.values()) }
		for x in pll_info['removable_info']['owning_info']:
			skill_name = gem_skill_id_dict[x['unit_removable_skill_id']]
			gem_owning_info[skill_name] = x['total_amount']
		# Generate user team information
		deck_info = []
		for i, deck in enumerate(pll_info['deck_info'],1):
			ids = [card_info[owning_id_dict[str(x['unit_owning_user_id'])]] for x in deck['unit_owning_user_ids']]
			if len(ids) == 9:
				deck_info.append(ids)
			else:
				print('Invalid team: {0}-th team only has {1} members placed'.format(i, len(ids)))
				deck_info.append(None)
		return card_info, gem_owning_info, deck_info
	def get_minaraishi_info(self, minaraishi_file, string_input=False):
		def get_card_levelup_info(card_info):
			member_index = int(card_info[0].split('.')[0]) - 1
			member_name, card_name = muse[member_index] if member_index < 10 else Aqours[member_index-10], card_info[3]
			card_id = member_card_name_to_id[(member_name, card_name)]
			card = raw_card_dict[card_id].copy()
			card.idolize(card_info[4][0] == '2')
			res = {
				'unit_id': cid_uid_dict[card_id],
				'card_id': card_id,
				'idolized': card.idolized,
				'level': card.level,
				'bond': card.bond,
				'skill_level': card_info[6],
				'slot_num': card_info[5],
				'equipped_gems':[]
			}
			return res
		minaraishi_info = json.loads(minaraishi_file if string_input else open(minaraishi_file).read())
		# minaraishi uses member name + card name as the prime key, need to convert the prime key to card ID
		member_card_name_to_id = {}
		for card_id, card in raw_card_dict.items():
			member_card_name_to_id[(card.member_name, card.card_name)] = card_id
		# Generate user card information
		card_info, owning_id_dict, index = dict(), dict(), 1
		for card in minaraishi_info['members']:
			try:
				card_info[str(index)] = get_card_levelup_info(card)
				index += 1
			except:
				print('Cannot generate card level-up info from', card)
		# Generate user gem information
		gem_owning_info = dict()
		for attr, d in minaraishi_info['idol_skills'].items():
			for gem_type, value in d.items():
				skill_name = attr.title() + ' ' + gem_type.title().replace('_1', ' (1st)').replace('_2', ' (2nd)').replace('_3', ' (3rd)')
				if 'Charm' in skill_name or 'Heal' in skill_name or 'Trick' in skill_name:
					skill_name = skill_name.replace('Smile', 'Princess').replace('Pure', 'Angel').replace('Cool', 'Empress')
				gem_owning_info[skill_name] = value
		# Generate user gem information
		deck_info = []
		return card_info, gem_owning_info, deck_info
	def get_SIT_info(self, SIT_file, string_input=False):
		def get_card_levelup_info(card_info):
			card_id = str(card_info['card']['id'])
			card = raw_card_dict[card_id].copy()
			card.idolize(card_info['idolized'])
			res = {
				'unit_id': card_info['card']['game_id'],
				'card_id': card_id,
				'idolized': card.idolized,
				'level': card.level,
				'bond': card.bond,
				'skill_level': card_info['skill'],
				'slot_num': card_info['skill_slots'],
				'equipped_gems':[]
			}
			return res
		SIT_info = json.loads(SIT_file if string_input else open(SIT_file).read())
		# Generate user card information
		card_info, index = dict(), 1
		for item in SIT_info:
			card_id = item['card']['id']
			try:
				card_info[str(index)] = get_card_levelup_info(item)
				index += 1
			except:
				print('Cannot generate card level-up info from card id, maybe it is a promo card', card_id)
		gem_owning_info, deck_info = {gem:9 for gem in list(gem_skill_id_dict.values())}, []
		return card_info, gem_owning_info, deck_info
	def filter(self, sel_func=None, sort_func=None, ascend=False):
		df = self.owned_card
		if sel_func is not None:
			df = df[df.apply(lambda x: sel_func(x), axis=1)]
		if sort_func is not None:
			aux = df.apply(lambda x: sort_func(x), axis=1)
			df = pd.concat([df, aux], axis=1)
			df.columns = list(df.columns)[:-1] + ['sort_val']
			df = df.sort_values(by='sort_val', ascending=ascend)
		return df
	def to_LLTB(self, filename='cards.666', rare=True):
		def gen_row(index, c):
			card = raw_card_dict[str(c['card_id'])].copy()
			card.idolize(c['idolized'])
			card.level_up(skill_level=c['skill'].level, slot_num=c['slot_num'])
			# name = str(index)+':'+card.card_name if card.card_name != ' ' else 'NOTSET'
			name = str(index)+':'+card.member_name if card.card_name != ' ' else 'NOTSET'
			info = [TB_member_dict[card.member_name], name] + adjusted_card_stat(card) + \
					get_skill_stat(card.skill, card.skill.level) + get_cskill_stat(card.cskill) + [card.slot_num]
			return '\t'.join([str(x) for x in info])+'\t'
		df = self.owned_card.copy()
		df = df[df.apply(lambda x: x.member_name in list(TB_member_dict.keys()), axis=1)]
		if rare:
			df = df[df.apply(lambda x: not x.promo and (x.rarity in ['UR','SSR'] or (x.rarity == 'SR' and x.idolized)), axis=1)]
		df = df[['card_id', 'idolized', 'skill', 'slot_num']]
		card_info = '\n'.join([gen_row(i,c) for i, c in df.iterrows()])
		gem_info = '-2 ' + ' '.join([str(np.minimum(self.owned_gem[x],9)) for x in TB_gem_skill_list])
		with codecs.open(filename, 'w', encoding='utf-16') as fp:
			fp.write('\n\n'.join([card_info, gem_info]))
		print('file saved to', filename)
	def to_WebATB(self, filename=None):
		user_json = {'unit_info':[{}]*len(self.raw_card), 'deck_info':[], 'removable_info':{'equipment_info':{}, 'owning_info':[{}]*len(self.owned_gem)}}
		for i, card in self.raw_card.items():
			res = {
				"unit_owning_user_id": i,
				"unit_id": cid_uid_dict[str(card.card_id)],
				"level": int(card.level),
				"love": int(card.bond),
				"rank": 1 + int(card.idolized),
				"unit_removable_skill_capacity": int(card.slot_num),
				"unit_skill_level": 1 if card.skill is None else int(card.skill.level)
			}
			user_json['unit_info'][int(i)-1] = res
		rev_gem_skill_id_dict = {v:k for k,v in gem_skill_id_dict.items()}
		for gem, value in self.owned_gem.items():
			gem_id = rev_gem_skill_id_dict[gem]
			user_json['removable_info']['owning_info'][gem_id-1] = {
				"total_amount": value,
				"unit_removable_skill_id": gem_id
			}
		if filename is None:
			return json.dumps(user_json)
		else:
			with open(filename, 'w') as fp:
				fp.write(json.dumps(user_json))
	def to_LLHelper(self, filename='submembers.sd'):
		def gen_item(card):
			return {
				"cardid": str(card.card_id),
			    "maxcost": str(card.slot_num),
			    "mezame": str(int(card.idolized)),
			    "skilllevel": "0" if card.skill is None else str(card.skill.level)
			}
		user_json = [gen_item(card) for index, card in self.raw_card.items() if card.rarity in ['SR', 'SSR', 'UR']]
		if filename is None:
			return json.dumps(user_json)
		else:
			with open(filename, 'w') as fp:
				fp.write(json.dumps(user_json))
			print('file saved to', filename)