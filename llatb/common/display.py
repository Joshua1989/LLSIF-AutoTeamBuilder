import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from IPython.display import HTML
from llatb.common.global_var import *
from llatb.common.config import misc_path, icon_path, gem_path
pd.set_option('display.max_colwidth', -1)

def gem_slot_pic(card, total_slot_num=8, show_cost=True, gem_size=35):
	gems, slot_num, max_slot_num = card.equipped_gems, card.slot_num, card.max_slot_num
	fmt ='<div style="float:left;*padding-left:0;"><img src="{0}" width={1}></div>'
	if show_cost:
		gem_name_list = []
		for gem in gems: 
			gem_name_list.extend([gem.name]*gem.cost)
		if len(gem_name_list) < slot_num:
			gem_name_list.extend(['empty'] * (slot_num-len(gem_name_list)))
		if len(gem_name_list) < max_slot_num:
			gem_name_list.extend(['placeholder'] * (max_slot_num-len(gem_name_list)))
		if len(gem_name_list) < total_slot_num:
			gem_name_list.extend(['void'] * (total_slot_num-len(gem_name_list)))
		divs = [fmt.format(gem_path(gem_name), gem_size) for gem_name in gem_name_list]
		result = '<div style="width:{0}px;">{1}<div>'.format(8*gem_size, ''.join(divs))
		return result
	else:
		divs = [fmt.format(gem_path(gem.name), gem_size) for gem in gems]
		result = '<div style="width:{0}px;">{1}<div>'.format(len(gems)*gem_size, ''.join(divs))
		return result


def view_card(card, show_gem=False, extra_col=[], gem_size=25):
	def get_summary(index, card, show_gem=False, ext_col=[]):
		res = {'index':index, 'CID': '<span> &nbsp {0} &nbsp </span>'.format(card.card_id)}
		# Generate HTML code for card view and skill
		res[col_name['view']] =  '<img src="{0}" width=60 />'.format(icon_path(card.card_id, card.idolized))
		if show_gem:
			res[col_name['view']] += gem_slot_pic1(card, show_cost=False, gem_size=gem_size)

		if card.skill is not None:
			temp = repr(card.skill).split(': ')
			fmt = '<p> <img style="float: left" src="{0}" width=15 /> {1} <br style="clear: both;"/> {2} <br/> {3} </p>'
			res[col_name['skill']] = fmt.format(misc_path(card.skill.effect_type) ,temp[0], *temp[1].split('. '))
		else:
			res[col_name['skill']] = '<p>{0}</p>'.format('NA')
		if card.cskill is not None:
			temp = repr(card.cskill).split('. ')
			func = lambda x: x.split(': ')[-1].replace('raise', 'Raise').replace('contribution ','')
			if temp[1] == '':
				res[col_name['skill']] += '<p>{0}</p>'.format(func(temp[0]))
			else:
				res[col_name['skill']] += '<p> {0} <br/> {1} </p>'.format(func(temp[0]), func(temp[1]))

		fmt = '<p style="color:{0};"> {1:<4d} <br/> {2:<4d} </p>'
		res[col_name['level']] = fmt.format('black', card.level, card.max_level)
		res[col_name['bond']] = fmt.format('black', card.bond, card.max_bond)
		res[col_name['hp']] = '<p style="color:orange;"> <b> &nbsp &nbsp {0} &nbsp </b> </p>'.format(card.hp)

		fmt = '<p style="color:{0};"> {1:<4d} <br/> {2:<4d} </p>'
		temp = card.card_strength(include_gem=True)
		res[col_name['smile']] = fmt.format('red', card.smile, temp['smile*'])
		res[col_name['pure']]  = fmt.format('green', card.pure, temp['pure*'])
		res[col_name['cool']]  = fmt.format('blue', card.cool, temp['cool*'])

		if card.skill is None:
			res['skill_gain'] = '<p>NA</p>'
		else:
			gain = card.skill.skill_gain()[0]
			if card.skill.effect_type in ['Strong Judge', 'Weak Judge']:
				res['skill_gain'] = '<p>{0:.4f}% <br/> covered </p>'.format(100*gain)
			elif card.skill.effect_type == 'Stamina Restore':
				res['skill_gain'] = '<p>{0:.4f} <br/> hp/note</p>'.format(gain)
			elif card.skill.effect_type == 'Score Up':
				res['skill_gain'] = '<p>{0:.4f} <br/> pt/note</p>'.format(gain)
		temp = card.general_strength()
		fmt = '<p> <span style="color:red">{0}</span> <br/> <span style="color:green">{1}</span> <br/> <span style="color:blue">{2}</span> </p> '
		func = lambda x: str(x['strength']) + ' (gem)'*int(x['use_skill_gem'])
		res['general_strength'] = fmt.format(func(temp['Smile']), func(temp['Pure']), func(temp['Cool']))
		res['skill_strength'] = fmt.format(temp['Smile']['skill_strength'], temp['Pure']['skill_strength'], temp['Cool']['skill_strength'])

		# If there are other columns to show
		for attr in ext_col: res[attr] = getattr(card, attr)
		return res

	col_name = {'view':'<p><b> Card View </b></p>', 'skill':'<p><b> Skill & Center Skill </b></p>'}
	col_name.update({ x:'<img src="{0}" width=25/>'.format(misc_path(x)) for x in ['level','bond','hp','smile','pure','cool'] })
	columns  = ['index', 'CID']
	columns += [col_name[x] for x in ['view', 'skill', 'level', 'bond', 'hp', 'smile', 'pure', 'cool']]
	columns += ['skill_gain', 'skill_strength', 'general_strength']
	columns += extra_col
	df = pd.DataFrame([get_summary(0, card, show_gem=show_gem, ext_col=extra_col)], columns=columns)
	df = df.set_index('index')
	df.index.name = ''
	return HTML(df.to_html(escape=False, index=False))

def view_cards(cards, show_gem=False, extra_col=[], gem_size=25):
	def get_summary(index, card, show_gem=False, ext_col=[]):
		res = {'index':int(index), 'CID': '<span> &nbsp {0} &nbsp </span>'.format(card.card_id)}
		# Generate HTML code for card view and skill
		res[col_name['view']] =  '<img src="{0}" width=60 />'.format(icon_path(card.card_id, card.idolized))
		if show_gem:
			gems = [gem.name for gem in card.equipped_gems]
			res[col_name['view']] += gem_slot_pic(card, gem_size=gem_size)

		if card.skill is not None:
			temp = repr(card.skill).split(': ')
			fmt = '<p> <img style="float: left" src="{0}" width=15 /> {1} <br style="clear: both;"/> {2} <br/> {3} </p>'
			res[col_name['skill']] = fmt.format(misc_path(card.skill.effect_type) ,temp[0], *temp[1].split('. '))
		else:
			res[col_name['skill']] = '<p>{0}</p>'.format('NA')
		if card.cskill is not None:
			temp = repr(card.cskill).split('. ')
			func = lambda x: x.split(': ')[-1].replace('raise', 'Raise').replace('contribution ','')
			if temp[1] == '':
				res[col_name['skill']] += '<p>{0}</p>'.format(func(temp[0]))
			else:
				res[col_name['skill']] += '<p> {0} <br/> {1} </p>'.format(func(temp[0]), func(temp[1]))

		fmt = '<p style="color:{0};"> {1:<4d} <br/> {2:<4d} </p>'
		res[col_name['level']] = fmt.format('black', card.level, card.max_level)
		res[col_name['bond']] = fmt.format('black', card.bond, card.max_bond)
		res[col_name['hp']] = '<p style="color:orange;"> <b> &nbsp &nbsp {0} &nbsp </b> </p>'.format(card.hp)

		fmt = '<p style="color:{0};"> {1} </p>'
		res[col_name['smile']] = fmt.format('red', card.smile)
		res[col_name['pure']]  = fmt.format('green', card.pure)
		res[col_name['cool']]  = fmt.format('blue', card.cool)

		if card.skill is None:
			res['skill_gain'] = '<p>NA</p>'
		else:
			gain = card.skill.skill_gain()[0]
			if card.skill.effect_type in ['Strong Judge', 'Weak Judge']:
				res['skill_gain'] = '<p>{0:.4f}% <br/> covered </p>'.format(100*gain)
			elif card.skill.effect_type == 'Stamina Restore':
				res['skill_gain'] = '<p>{0:.4f} <br/> hp/note</p>'.format(gain)
			elif card.skill.effect_type == 'Score Up':
				res['skill_gain'] = '<p>{0:.4f} <br/> pt/note</p>'.format(gain)

		# If there are other columns to show
		for attr in ext_col: res[attr] = getattr(card, attr)
		return res

	col_name = {'view':'<p><b> Card View </b></p>', 'skill':'<p><b> Skill & Center Skill </b></p>'}
	col_name.update({ x:'<img src="{0}" width=25/>'.format(misc_path(x)) for x in ['level','bond','hp','smile','pure','cool'] })
	columns  = ['index', 'CID']
	columns += [col_name[x] for x in ['view', 'skill', 'level', 'bond', 'hp', 'smile', 'pure', 'cool']]
	columns += ['skill_gain'] + extra_col

	if isinstance(cards, pd.core.frame.DataFrame):
		data = [get_summary(index, card, show_gem, ext_col=extra_col) for index, card in cards.iterrows()]
	elif type(cards) == list:
		data = [get_summary(index, card, show_gem, ext_col=extra_col) for index, card in enumerate(cards,1)]
	elif  type(cards) == dict:
		data = [get_summary(index, card, show_gem, ext_col=extra_col) for index, card in cards.items()]
		data.sort(key=lambda x: x['index'])
	else:
		print('Input must be a list, a dict, or a pandas DataFrame!')
		raise
	df = pd.DataFrame(data, columns=columns)
	df = df.set_index('index')
	df.index.name = ''
	return HTML(df.to_html(escape=False))

def view_team(team, show_gem=False, extra_col=[], gem_size=25):
	def get_summary(index, card, show_gem=False, ext_col=[]):
		res = {'index':index, 'CID': '<span> &nbsp {0} &nbsp </span>'.format(card.card_id)}
		# Generate HTML code for card view and skill
		res[col_name['view']] =  '<img src="{0}" width=60 />'.format(icon_path(card.card_id, card.idolized))
		if show_gem:
			gems = [gem.name for gem in card.equipped_gems]
			res[col_name['view']] += gem_slot_pic(card, gem_size=gem_size)

		if card.skill is not None:
			gain = card.skill.skill_gain()[0]
			if card.skill is None:
				skill_gain_str = 'NA'
			elif card.skill.effect_type in ['Strong Judge', 'Weak Judge']:
				skill_gain_str = '{0:.4f}% covered '.format(100*gain)
			elif card.skill.effect_type == 'Stamina Restore':
				skill_gain_str = '{0:.4f} hp/note'.format(gain)
			elif card.skill.effect_type == 'Score Up':
				skill_gain_str = '{0:.4f} pt/note'.format(gain)

			temp = repr(card.skill).split(': ')
			fmt = '<p> <img style="float: left" src="{0}" width=15 /> {1} <br style="clear: both;"/> {2} <br/> {3} Gain: {4} </p>'
			res[col_name['skill']] = fmt.format(misc_path(card.skill.effect_type) ,temp[0], *temp[1].split('. '), skill_gain_str)			
		else:
			res[col_name['skill']] = '<p>{0}</p>'.format('NA')
		if card.cskill is not None:
			temp = repr(card.cskill).split('. ')
			func = lambda x: x.split(': ')[-1].replace('raise', 'Raise').replace('contribution ','')
			if temp[1] == '':
				res[col_name['skill']] += '<p>{0}</p>'.format(func(temp[0]))
			else:
				res[col_name['skill']] += '<p> {0} <br/> {1} </p>'.format(func(temp[0]), func(temp[1]))

		fmt = '<p style="color:{0};"> {1:<4d} <br/> {2:<4d} </p>'
		res[col_name['level']] = fmt.format('black', card.level, card.max_level)
		res[col_name['bond']] = fmt.format('black', card.bond, card.max_bond)
		res[col_name['hp']] = '<p style="color:orange;"> <b> &nbsp &nbsp {0} &nbsp </b> </p>'.format(card.hp)

		fmt = '<p style="color:{0};"> {1:<4d} <br/> {2:<4d} <br/> {3:<4d} </p>'
		res[col_name['smile']] = fmt.format('red', card.smile, disp_card_attr[index][0], final_card_attr[index][0])
		res[col_name['pure']]  = fmt.format('green', card.pure, disp_card_attr[index][1], final_card_attr[index][1])
		res[col_name['cool']]  = fmt.format('blue', card.cool, disp_card_attr[index][2], final_card_attr[index][2])

		# If there are other columns to show
		for attr in ext_col: res[attr] = getattr(card, attr)
		return res

	team_strength_info = team.team_strength()
	disp_card_attr = team_strength_info['displayed_card_attr']
	final_card_attr = team_strength_info['final_card_attr']
	col_name = {'view':'<p><b> Card View </b></p>', 'skill':'<p><b> Skill & Center Skill </b></p>'}
	col_name.update({ x:'<img src="{0}" width=25/>'.format(misc_path(x)) for x in ['level','bond','hp','smile','pure','cool'] })
	columns  = ['index', 'CID']
	columns += [col_name[x] for x in ['view', 'skill', 'level', 'bond', 'hp', 'smile', 'pure', 'cool']]
	columns += extra_col
	data = [get_summary(index, card, show_gem, ext_col=extra_col) for index, card in enumerate(team.card_list)]
	df = pd.DataFrame(data, columns=columns)
	pos_name = ['L1', 'L2', 'L3', 'L4', 'C', 'R4', 'R3', 'R2', 'R1']
	df['index'] = pos_name
	df = df.set_index('index')
	df.index.name = ''

	# For Team input, add header for team stats
	col = ['team_total', 'team_center_skill_bonus', 'center_SIS_bonus', 'guest_center_skill_bonus']
	df_header = pd.DataFrame({c:team_strength_info[c] for c in col}, columns=col, index=attr_list)
	df_header.columns = ['Team Total', 'Center Skill Bonus', 'Center SIS Bonus', 'Support Member Bonus']
	header = '<div align="left"> {0} </div>'.format(df_header.to_html())
	# Bold center skill of the center member
	temp =[str(x) for x in BeautifulSoup(df.loc['C', col_name['skill']], "html.parser").find_all('p')]
	center = team.center()
	if len(temp) == 2:
		start_str = '<p style="color:{0};"><b><u>'.format(attr_color[center.main_attr])
		temp[-1] = temp[-1].replace('<p>',start_str).replace('</p>','</u></b></p>')
		df.loc['C', col_name['skill']] = ''.join(temp)
	# For all member satisfying center skill bonus range, 
	if center.cskill.bonus_range is not None:
		bonus_range = groups[center.cskill.bonus_range]
		start_str = '<span style="background-color:{0};color:white">'.format(attr_color[center.main_attr])
		for index, card in zip(pos_name, team.card_list):
			if card.main_attr == center.main_attr:
				df.loc[index, 'CID'] = df.loc[index, 'CID'].replace('<span>','<span><u>').replace('</u></span>','</span>')
			if card.member_name in bonus_range:
				df.loc[index, 'CID'] = df.loc[index, 'CID'].replace('<span>',start_str)
	# Place center card first
	df = df.loc[['C', 'L1', 'L2', 'L3', 'L4', 'R4', 'R3', 'R2', 'R1']]
	return HTML(header + df.to_html(escape=False))

def view_live(live):
	song_name = '<p style="color:{0};">{1}</p>'.format(attr_color[live.attr], live.name)
	df_head = pd.DataFrame({'Song Name': [song_name]})
	df_head['Group'] = live.group
	df_head['Difficulty'] = live.difficulty
	df_head['Total Note'] = live.note_number
	df_head['Duration'] = live.duration
	df = live.summary.copy()
	pos_name = ['L1', 'L2', 'L3', 'L4', 'C', 'R4', 'R3', 'R2', 'R1']
	df.index = [pos_name[9-x] if type(x)==int else x for x in list(df.index)]
	df = df.loc[pos_name+['total']]
	df = df.applymap(lambda x: str(int(x)) if np.isclose(x,round(x)) else '{0:.3f}'.format(x)).transpose()
	return HTML(df_head.to_html(escape=False, index=False) + df.to_html())