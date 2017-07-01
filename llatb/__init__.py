# Load sub-packages
import numpy as np
import pandas as pd
from pathlib import Path
from IPython.display import HTML

import llatb.common
from llatb.common import config, global_var
from llatb import skill
from llatb.framework import Card, Team, Live, DefaultLive
from llatb.importer.game_data import GameData
from llatb.simulator import Simulator
from llatb.advanced import TeamBuilder

def update_data():
	llatb.common.util.update_card_data()
	llatb.common.util.update_live_data()

def html_view(item_to_show, show_gem=False, extra_col=[]):
	if isinstance(item_to_show, Card):
		return llatb.common.display.view_card(item_to_show, show_gem=show_gem, extra_col=extra_col)
	elif isinstance(item_to_show, Team):
		return llatb.common.display.view_team(item_to_show, show_gem=show_gem, extra_col=extra_col)
	elif isinstance(item_to_show, pd.core.frame.DataFrame):
		return llatb.common.display.view_cards(item_to_show, show_gem=show_gem, extra_col=extra_col)
	elif type(item_to_show) in [dict, list]:
		return llatb.common.display.view_cards(item_to_show, show_gem=show_gem, extra_col=extra_col)
	elif isinstance(item_to_show, Live):
		return llatb.common.display.view_live(item_to_show)

def skill_type_table():
	user_profile = GameData()
	df = user_profile.owned_card
	df = df[df.rarity!='N'].copy()
	df['skill_type'] = df.skill.apply(lambda x: None if x is None else (x.effect_type, x.trigger_type))
	df['card_type'] = df.apply(lambda x: (x.rarity, x.main_attr), axis=1)
	df = pd.concat((df, pd.get_dummies(df['card_type'])), axis=1)
	df_group = df.groupby(['skill_type'])[df['card_type'].drop_duplicates().values.tolist()].sum().sort_index()
	return df_group

if Path(config.live_archive_dir).is_file():
	from llatb.framework.live import live_basic_data
	def show_live_list(group=None, attr=None, diff_level=None):
		def match_func(x):
			res = True
			if group is not None: res &= x.group==group
			if attr is not None: res &= x.attr==attr
			if diff_level is not None: res &= x.diff_level==diff_level
			return res
		df = live_basic_data[live_basic_data.apply(lambda x: match_func(x), axis=1)].copy()
		df['cover'] = df['cover'].apply(lambda x: '<img src="{0}" width=100 />'.format(x))
		df['name'] = df.apply(lambda x: '<p style="color:{0};">{1}</p>'.format(global_var.attr_color[x['attr']], x['name']), axis=1)
		df = df[['cover', 'name', 'diff_level', 'note_number', 'diff_star']]
		df.columns = ['<p>{0}</p>'.format(x) for x in df.columns]
		return HTML(df.to_html(escape=False, index=False))