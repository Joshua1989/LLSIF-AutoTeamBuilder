import numpy as np
import urllib.request, json
from bs4 import BeautifulSoup
from pathlib import Path
from llatb.common.config import *
from llatb.common.global_var import attr_list, bonus_range_list
from llatb.framework.card import Card
from llatb.framework.team import Team

def update_card_data(card_id_list=None, download=False):
	def parse_card_info_html(card_id):
		card_url = card_info_url(card_id)
		card_info = {'card_id':card_id, 'rarity':None, 'stats_list':None, 'skill':None, 'cskill':None}
		if 'http' in card_url:
			soup = BeautifulSoup(urllib.request.urlopen(card_url).read().decode('UTF-8'), "html.parser")
			card_info['member_name'] = soup.find_all('a', {'href':'/card/'+str(card_id)})[0].string.replace('Yohane', 'Yoshiko')
		else:
			soup = BeautifulSoup(open(card_url).read(), "html.parser")
			card_info['member_name'] = soup.find_all('a', {'href':str(card_id)+''})[0].string
		card_info['promo'] = len(soup.find_all('div', {'id':'iswitch'})) == 0
		try:
			s = soup.find_all('script', {'id':'iv'})[0].string
			stats_dict = json.loads(s[s.find('{'):s.rfind('}')+1])[str(card_id)]
			card_info['rarity'] = {40:'N', 60:'R', 80:'SR', 90:'SSR', 100:'UR'}[stats_dict['level_max']]
			card_info['card_name'] = ' ' if card_info['rarity'] in ['N','R'] or card_info['promo'] else soup.h2.small.string
			card_info['stats_list'] = stats_dict['stats']
			card_info['main_attr'] = attr_list[np.argmax(stats_dict['stats'][0][:3])]
		except:
			print('Did not find stats dict')
			return None
		card_info['skill'], card_info['cskill'] = None, None
		if stats_dict['skill'] is not None:
			# Skill name
			card_info['skill'], skill_info = dict(), soup.find_all('div', {'class':'skill box'})[0]
			card_info['skill']['name'] = skill_info.find_all('span', {'class':'content'})[0].string
			# Skill level data
			temp = np.array(stats_dict['skill'], dtype=int).T
			card_info['skill']['odds_list'], card_info['skill']['rewards_list'] = temp[0].tolist(), temp[1].tolist()
			# Skill effect type
			skill_info = skill_info.find_all('div', {'class':'description'})[0].find_all('span', class_=lambda x: x != 'varying')
			temp = skill_info[1].contents[0] 
			if temp == '\nto raise the accuracy of great notes for ':
				card_info['skill']['effect_type'] = 'Weak Judge'
			elif temp == '\nto add ':
				card_info['skill']['effect_type'] = 'Score Up'
			elif temp == '\nto restore ':
				card_info['skill']['effect_type'] = 'Stamina Restore'
			elif temp == '\nto raise the accuracy of all notes for ':
				card_info['skill']['effect_type'] = 'Strong Judge'
			else:
				print('Incorrect skill effect type!')
				raise
			# Skill trigger type and trigger count
			temp = skill_info[2].contents[-1]
			if temp == ' seconds.\n':
				card_info['skill']['trigger_type'] = 'Time'
				card_info['skill']['trigger_count'] = int(skill_info[2].span.string)
			elif temp == ' notes.\n':
				card_info['skill']['trigger_type'] = 'Note'
				card_info['skill']['trigger_count'] = int(skill_info[2].span.string)
			elif temp == ' notes are hit in a row.\n':
				card_info['skill']['trigger_type'] = 'Combo'
				card_info['skill']['trigger_count'] = int(skill_info[2].span.string)
			elif temp == '.\n':
				card_info['skill']['trigger_type'] = 'Score'
				card_info['skill']['trigger_count'] = int(skill_info[2].span.string)
			elif temp == ' perfect notes are hit.\n':
				card_info['skill']['trigger_type'] = 'Perfect'
				card_info['skill']['trigger_count'] = int(skill_info[2].span.string)
			elif temp == '\nTriggers when a perfect star icon is hit.\n':
				card_info['skill']['trigger_type'] = 'Star'
				card_info['skill']['trigger_count'] = 1
			else:
				print('Incorrect skill trigger type!')
				raise
			# Center Skill name and main attribute
			card_info['cskill'], cskill_info = dict(), soup.find_all('div', {'class':'skill box'})[1]
			card_info['cskill']['name'] = cskill_info.find_all('span', {'class':'content'})[0].string
			card_info['cskill']['main_attr'] = card_info['main_attr']
			# Center Skill base_attr, main_ratio
			ratio_data = cskill_info.find_all('span', {'class':'varying'})
			temp = list(cskill_info.find_all('div', {'class':'description'})[0])[2]
			if '%.' in temp:
				card_info['cskill']['base_attr'] = card_info['cskill']['main_attr']
			else:
				card_info['cskill']['base_attr'] = temp.split('.')[0].split(' ')[-1]
			card_info['cskill']['main_ratio'] = int(ratio_data[0].string)
			# Center Skill bonus_range, bonus_ratio
			if card_info['rarity'] not in ['SSR', 'UR'] or card_info['promo'] == True:
				card_info['cskill']['bonus_range'], card_info['cskill']['bonus_ratio'] = None, None
			else:
				bonus_range = temp.split('contribution of ')[-1].split(' member')[0]
				bonus_range = bonus_range.replace('first','1st').replace('second','2nd').replace('third','3rd')
				if bonus_range not in bonus_range_list:
					print('Invalid member group: ' + bonus_range)
					raise
				card_info['cskill']['bonus_range'] = bonus_range
				card_info['cskill']['bonus_ratio'] = int(ratio_data[1].string)
		return card_info
	card_basic_stat = dict()
	if Path(card_archive_dir).is_file():
		card_basic_stat = json.loads(open(card_archive_dir).read())
	key_list = list(card_basic_stat.keys())
	last_card_id = 0 if len(key_list) == 0 else max([int(x) for x in key_list])

	if card_id_list is None:
		soup = BeautifulSoup(urllib.request.urlopen(card_info_base_url).read().decode('UTF-8'), "html.parser")
		items = soup.find_all(lambda tag: tag.name == 'td' and tag.get('class') == ['ar'] and tag.string.replace('#','').isdigit())
		card_id_list = list(range(1,len(items)+1))

	card_id_list = [x for x in card_id_list if x > last_card_id]
	for card_id in card_id_list:
		print('Processing card {0}'.format(card_id))
		if str(card_id) not in key_list:
			print('Discover unarchived card {0}'.format(card_id))
			temp = parse_card_info_html(card_id)
			if temp is not None:
				card_basic_stat[str(card_id)] = temp
			else:
				print('Card {0} is a support member'.format(card_id))
	with open(card_archive_dir, 'w') as fp:
	    json.dump(card_basic_stat, fp)
	print('Basic card data has been saved in', card_archive_dir)

def update_live_data(download=False):
	text = urllib.request.urlopen('http://c.dash.moe/live').read().decode('utf-8')
	for line in text.split('\n'):
		if 'lives:' in line:
			live_json = json.loads(line[line.find('['):line.rfind(']')+1])
	
	live_data = {'group':[], 'attr':[], 'name':[], 'cover':[], 'diff_level':[], 'diff_star':[], 'note_number':[], 'file_dir':[]}
	group_map, attr_map = {1:"μ's", 2:'Aqours'}, {1:'Smile', 2:'Pure', 3:'Cool'}
	diff_map = {1:'Easy', 2:'Normal', 3:'Hard', 4:'Expert', 6:'Master', 7:'Challenge'}
	for song in live_json:
		name, cover = song['name'], 'https://r.llsif.win/'+song['icon']
		group = group_map[song['member_category']]
		attr = attr_map[song['attribute']]
		for live in song['difficulties']:
			live_data['name'].append(name)
			live_data['cover'].append(cover)
			live_data['attr'].append(attr)
			live_data['group'].append(group)
			live_data['diff_level'].append(diff_map[live['difficulty']])
			live_data['diff_star'].append(live['stage_level'])
			live_data['note_number'].append(live['s_rank_combo'])
			live_data['file_dir'].append(live['asset'])
	with open(live_archive_dir, 'w') as fp:
	    json.dump(live_data, fp)
	print('Basic live data has been saved in', live_archive_dir)