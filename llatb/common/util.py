import numpy as np
import pandas as pd
import urllib.request, sqlite3, json
from bs4 import BeautifulSoup
from pathlib import Path
from llatb.common.config import *
from llatb.framework.card import Card
from llatb.framework.team import Team
from llatb.common.global_var import Aqours

def update_card_data():
	def card_summary(unit_id):
		unit_info = df_unit.loc[unit_id]
		attr_dict = {1:'Smile', 2:'Pure', 3:'Cool'}
		# Generate stats list
		level_up_info = df_level_up.loc[unit_info['unit_level_up_pattern_id']]
		stats_list = np.array([
			unit_info['smile_max'] - level_up_info['smile_diff'],
			unit_info['pure_max'] - level_up_info['pure_diff'],
			unit_info['cool_max'] - level_up_info['cool_diff'],
			level_up_info['sale_price'],
			level_up_info['merge_exp'],
			unit_info['hp_max'] - level_up_info['hp_diff']
		]).T.tolist()
		# Generate skill info
		if np.isnan(unit_info['default_unit_skill_id']):
			skill = None
		else:
			skill_info = df_skill.loc[unit_info['default_unit_skill_id']]
			skill_level_info = df_skill_level.loc[unit_info['default_unit_skill_id']]
			trigger_type_dict = {1:'Time', 3:'Note', 4:'Combo', 5:'Score', 6:'Perfect', 12:'Star'}
			effect_type_dict = {4:'Weak Judge', 5:'Strong Judge', 9:'Stamina Restore', 11:'Score Up'}
			skill = {
				'name': skill_info['name'],
				'trigger_type': trigger_type_dict[skill_info['trigger_type']],
				'trigger_count': int(skill_level_info['trigger_value'].values[0]),
				'effect_type': effect_type_dict[skill_info['skill_effect_type']],
				'odds_list': skill_level_info['activation_rate'].values.tolist(),
			}
			if skill['effect_type'] in ['Weak Judge', 'Strong Judge']:
				skill['rewards_list'] = skill_level_info['discharge_time'].values.tolist()
			else:
				skill['rewards_list'] = skill_level_info['effect_value'].values.tolist()
		# Generate center skill info
		if np.isnan(unit_info['default_leader_skill_id']):
			cskill = None
		else:
			cskill1_info = df_cskill1.loc[unit_info['default_leader_skill_id']]
			temp = cskill1_info['leader_skill_effect_type']
			if len(str(temp)) == 1:
				main_attr, base_attr = attr_dict[temp], attr_dict[temp]
			else:
				main_attr, base_attr = attr_dict[temp%10], attr_dict[int((temp-100)/10)]
			if unit_info['default_leader_skill_id'] not in df_cskill2.index:
				bonus_range, bonus_ratio = None, None
			else:
				cskill2_info = df_cskill2.loc[unit_info['default_leader_skill_id']]
				tag_dict = {1:'1st-year', 2:'2nd-year', 3:'3rd-year', 4:"μ's", 5:'Aqours',
							6:'Printemps', 7:'lily white', 8:'BiBi',
							9:'CYaRon！', 10:'AZALEA',  11:'Guilty Kiss'}
				bonus_range, bonus_ratio = tag_dict[cskill2_info['member_tag_id']], int(cskill2_info['effect_value'])
			cskill = {
				'name': cskill1_info['name'],
				'main_attr': main_attr,
				'base_attr': base_attr,
				'main_ratio': int(cskill1_info['effect_value']),
				'bonus_range': bonus_range,
				'bonus_ratio': bonus_ratio
			}
		# Generate whole summary
		rarity_dict = {1:'N', 2:'R', 3:'SR', 4:'UR', 5:'SSR'}
		if id_crown_dict.get(unit_info['unit_number']) is None:
			card_name = ' ' if unit_info['eponym'] is None else unit_info['eponym']
		else:
			card_name = id_crown_dict.get(unit_info['unit_number'])
		card_info = {
			'promo': bool(unit_info['is_promo']),
			'card_name': card_name,
			'card_id': int(unit_info['unit_number']),
			'main_attr': attr_dict[unit_info['attribute_id']],
			'member_name': unit_info['name'],
			'stats_list': stats_list,
			'cskill': cskill,
			'skill': skill,
			'rarity': rarity_dict[unit_info['rarity']]
		}
		return unit_info['unit_number'], card_info

	print('Downloading minaraishi\'s member.json')
	minaraishi = json.loads(urllib.request.urlopen(minaraishi_json_url).read().decode('utf-8'))
	id_crown_dict = dict()
	for member, d1 in minaraishi.items():
		for attribute, d2 in d1.items():
			for rarity, d3 in d2.items():
				for crown, d4 in d3.items():
					id_crown_dict[d4['id']] = crown

	print('Downloading latest unit.db_')
	opener = urllib.request.URLopener()
	opener.addheader('User-Agent', 'whatever')
	opener.retrieve(unit_db_download_url, unit_db_dir)

	print('Generating basic card stats')
	conn = sqlite3.connect(unit_db_dir)
	df_level_up = pd.read_sql('SELECT * FROM unit_level_up_pattern_m', con=conn, index_col='unit_level_up_pattern_id')
	df_skill = pd.read_sql('SELECT * FROM unit_skill_m', con=conn, index_col='unit_skill_id')
	df_skill_level = pd.read_sql('SELECT * FROM unit_skill_level_m', con=conn, index_col='unit_skill_id')
	df_cskill1 = pd.read_sql('SELECT * FROM unit_leader_skill_m', con=conn, index_col='unit_leader_skill_id')
	df_cskill2 = pd.read_sql('SELECT * FROM unit_leader_skill_extra_m', con=conn, index_col='unit_leader_skill_id')
	df_unit = pd.read_sql('SELECT * FROM unit_m', con=conn, index_col='unit_id')
	df_unit = df_unit[df_unit['unit_number']>0]
	df_unit['is_support'] = df_unit['smile_max'] == 1
	df_unit['is_promo'] = df_unit.apply(lambda x: x['smile_max'] > 1 and
										x['normal_icon_asset'] == x['rank_max_icon_asset'], axis=1)
	# Generate card basic stat and save it to JSON
	card_basic_stat = dict()
	for unit_id, row in df_unit.iterrows():
		if not row['is_support']:
			card_id, card_info = card_summary(unit_id)
			card_basic_stat[str(card_id)] = card_info

	print('Generating basic card stats for Region Promo Set')
	conn = sqlite3.connect(unit_aux_db_dir)
	df_level_up = pd.read_sql('SELECT * FROM unit_level_up_pattern_m', con=conn, index_col='unit_level_up_pattern_id')
	df_skill = pd.read_sql('SELECT * FROM unit_skill_m', con=conn, index_col='unit_skill_id')
	df_skill_level = pd.read_sql('SELECT * FROM unit_skill_level_m', con=conn, index_col='unit_skill_id')
	df_cskill1 = pd.read_sql('SELECT * FROM unit_leader_skill_m', con=conn, index_col='unit_leader_skill_id')
	df_cskill2 = pd.read_sql('SELECT * FROM unit_leader_skill_extra_m', con=conn, index_col='unit_leader_skill_id')
	df_unit = pd.read_sql('SELECT * FROM unit_m', con=conn, index_col='unit_id')
	df_unit = df_unit[df_unit['unit_number']>0]
	df_unit['is_support'] = df_unit['smile_max'] == 1
	df_unit['is_promo'] = df_unit.apply(lambda x: x['smile_max'] > 1 and
										x['normal_icon_asset'] == x['rank_max_icon_asset'], axis=1)
	# Generate card basic stat and save it to JSON
	for unit_id, row in df_unit.iterrows():
		if not row['is_support'] and unit_id in list(range(1243,1252)):
			card_id, card_info = card_summary(unit_id)
			card_info['member_name'] = Aqours[unit_id-1243]
			card_basic_stat[str(card_id)] = card_info

	with open(card_archive_dir, 'w') as fp:
	    json.dump(card_basic_stat, fp)
	print('Basic card data has been saved in', card_archive_dir)

def update_live_data(download=False):
	def live_summary(live_setting_id):
		group_dict = {1:"μ's", 2:'Aqours'}
		attr_dict = {1:'Smile', 2:'Pure', 3:'Cool'}
		diff_dict = {1:'Easy', 2:'Normal', 3:'Hard', 4:'Expert', 6:'Master'}
		setting = df_live_setting.loc[live_setting_id]
		track_info = df_live_track.loc[setting['live_track_id']]
		live_info = {
			'cover': cover_path(setting['live_icon_asset']),
			'name': track_info['name'],
			'group': group_dict[track_info['member_category']],
			'attr': attr_dict[setting['attribute_icon_id']],
			'note_number': int(setting['s_rank_combo']),
			'diff_level': diff_dict[setting['difficulty']],
			'diff_star': int(setting['stage_level']),
			'file_dir': live_path(setting['notes_setting_asset'])
		}
		return live_info

	print('Downloading latest live.db_')
	opener = urllib.request.URLopener()
	opener.addheader('User-Agent', 'whatever')
	opener.retrieve(live_db_download_url, live_db_dir)

	print('Generating basic live stats')
	conn = sqlite3.connect(live_db_dir)
	df_live_track = pd.read_sql('SELECT * FROM live_track_m', con=conn, index_col='live_track_id')
	df_live_setting = pd.read_sql('SELECT * FROM live_setting_m', con=conn, index_col='live_setting_id')
	live_data = [live_summary(live_setting_id) for live_setting_id, row in df_live_setting.iterrows() if row['difficulty']!=5]

	with open(live_archive_dir, 'w') as fp:
	    json.dump(live_data, fp)
	print('Basic live data has been saved in', live_archive_dir)