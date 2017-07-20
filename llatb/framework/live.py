import numpy as np
import pandas as pd
import json, urllib.request
from llatb.common.config import live_archive_dir, live_path
from llatb.common.global_var import *

# Default presumption: A live contain 700 notes and lasts for 120 seconds
# 10% notes are star note, 8% notes are long note, 4% notes are swing note
# Player has team with strength 80000, 95% of the taps are Perfect, the rest 5% are Great
default_setting = {	'note_number':700, 'duration':120, 'star_density':0.1, 
					'note_type_dist':{'normal_density':0.88, 'long_density':0.08, 'swing_density':0.04}, 
					'perfect_rate':0.95, 'team_strength':80000}

# Load basic stats from data_base.json
try:
	live_basic_data = pd.read_json(live_archive_dir)
except:
	print('Live data base json file {0} does not exist!'.format(live_archive_dir))

class Live:
	def __init__(self, name, difficulty, perfect_rate=0.95, local_dir=None):
		try:
			info = live_basic_data[live_basic_data.apply(lambda x: x['name']==name and x['diff_level']==difficulty, axis=1)].iloc[0]
		except:
			print('Live data of {0} {1} not found!'.format(name, difficulty))
			raise
		self.name, self.difficulty = name, difficulty
		self.cover = info.cover
		self.group, self.attr = info.group, info.attr
		if local_dir is None:
			req = urllib.request.Request(info.file_dir, data=None, headers={'User-Agent': 'whatever'})
			temp = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
		else:
			try:
				temp = json.loads(open(local_dir+info.file_dir.split('/')[-1]).read())
			except:
				req = urllib.request.Request(info.file_dir, data=None, headers={'User-Agent': 'whatever'})
				temp = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
		df = pd.DataFrame(temp, index=list(range(1,len(temp)+1)))
		df = df.assign(token=df.effect==2, long=df.effect.apply(lambda x: x == 3), 
					   star=df.effect==4, swing=df.effect.apply(lambda x: x in [11,13]))
		df['tap'] = df.apply(lambda x: not (x.long or x.swing), axis=1)
		self.note_list = df.copy()
		# Compute end time for each note
		self.note_number, self.duration = len(df), (df.timing_sec + df.long*df.effect_value).max()
		# Compute all useful stats
		self.perfect_rate = perfect_rate
		self.compute_stat()
	def __repr__(self):
		return '{0} {1}: attr={2}, duration={3}'.format(self.name, self.difficulty, self.attr, self.duration)
	def compute_stat(self):
		df = self.note_list.copy()
		df.timing_sec = df.timing_sec + df.effect_value * df.long
		df = df.sort_values(by='timing_sec', ascending=True)
		df.index = [i for i in range(1, len(df)+1)]
		# Compute all factors that matter scoring, under presumed perfect rate
		p, alpha, beta = self.perfect_rate, accuracy_factor['Perfect'], accuracy_factor['Great']
		df['judge_factor'] = df.long.apply(lambda x: ( alpha*p + beta*(1-p) )**(1+x) )
		df['note_factor'] = df.apply(lambda x: long_factor**x.long * swing_factor**x.swing, axis=1)
		df['combo_factor'] = [combo_factor(i) for i in range(1,len(df)+1)]
		df['total_factor'] = df.combo_factor * df.note_factor * df.judge_factor
		# Compute stats for each position
		note_stat = df.groupby(by='position')[['tap', 'long', 'swing', 'star', 'token']].sum().applymap(int)
		note_stat['note_factor'] = df.groupby(by='position')['note_factor'].sum()
		note_stat['total_factor'] = df.groupby(by='position')['total_factor'].sum()
		if len(note_stat) < 9:
			missing_pos = [x for x in range(1,10) if x not in note_stat.index]
			for pos in missing_pos:
				note_stat = note_stat.append(pd.DataFrame(0*note_stat.sum(), columns=[pos]).transpose())
			note_stat = note_stat.sort_index()
		note_stat = note_stat.append(pd.DataFrame(note_stat.sum(), columns=['total']).transpose())
		note_stat['weight'] = note_stat['total_factor'] / note_stat.loc['total','total_factor']
		# Save useful statistics as member variables
		self.summary = note_stat
		self.star_density = note_stat.loc['total','star'] / self.note_number

		self.note_type_dist = dict()
		self.note_type_dist['normal_density'] = note_stat.loc['total','tap'] / self.note_number
		self.note_type_dist['long_density'] = note_stat.loc['total','long'] / self.note_number
		self.note_type_dist['swing_density'] = note_stat.loc['total','swing'] / self.note_number

		self.average_bonus = note_stat.loc['total','total_factor']/self.note_number
		self.strength_per_pt_tap = (1/base_score_factor) / (note_stat.loc['total','total_factor']/self.note_number)
		self.pts_per_strength = base_score_factor * note_stat.loc['total','total_factor']
		self.combo_weight_fraction = self.summary.weight.values[-2::-1]

class DefaultLive:
	def __init__(self, name, difficulty='Master', perfect_rate=0.95, setting=default_setting):
		self.name = name
		self.difficulty = difficulty
		# Set parameter for live and player performance
		param = default_setting.copy()
		param.update(setting)
		param['note_number'] = {'Easy':110, 'Normal':200, 'Hard':350, 'Expert':500, 'Master':700}[difficulty]

		temp = name.split()
		if 'Default' != temp[0]: raise
		self.group, self.attr = temp[1], temp[2]

		# Presumed live parameter
		self.note_number, self.duration = param['note_number'], param['duration']
		self.star_density   = param['star_density']
		self.note_type_dist = param['note_type_dist']

		# Presumed player parameter
		self.perfect_rate = perfect_rate
		# Average combo factor if achieve FC
		combo_weight = np.array([combo_factor(i+1) for i in range(self.note_number)]).mean()
		# Average accuracy factor under presumed player perfect rate and live note type fractions
		note_judge_factor = self.perfect_rate*accuracy_factor['Perfect'] + (1-self.perfect_rate)*accuracy_factor['Great']
		normal_density, swing_density, long_density = param['note_type_dist']['normal_density'], param['note_type_dist']['swing_density'], param['note_type_dist']['long_density']
		note_judge_weight = note_judge_factor*(normal_density+swing_factor*swing_density) + note_judge_factor**2 * long_factor*long_density
		# Corrected strength per point per tap
		self.average_bonus = combo_weight*note_judge_weight
		self.strength_per_pt_tap = (1/base_score_factor) / (combo_weight*note_judge_weight)
		self.pts_per_strength = self.note_number / self.strength_per_pt_tap
		self.combo_weight_fraction = np.ones(9)/9

class MFLive:
	def __init__(self, name_list, difficulty, perfect_rate=0.95, local_dir=None):
		self.difficulty, self.perfect_rate = difficulty, perfect_rate
		names, groups, attrs, covers, file_dirs = [], [], [], [], []
		for name in name_list:
			try:
				info = live_basic_data[live_basic_data.apply(lambda x: x['name']==name and x['diff_level']==difficulty, axis=1)].iloc[0]
			except:
				print('Live data of {0} {1} not found!'.format(name, difficulty))
				raise
			names.append(name)
			covers.append(info.cover)
			groups.append(info.group)
			attrs.append(info.attr)
			file_dirs.append(info.file_dir)

		if len(set(groups)) > 1 or len(set(attrs)) > 1:
			print('Group and attribute must be same!')
			raise
		self.name = ', '.join(names)
		self.group, self.attr = groups[0], attrs[0]
		self.cover = covers[0]

		self.note_number = 0
		dfs, durations = [], []
		for i, file_dir in enumerate(file_dirs):
			if local_dir is None:
				req = urllib.request.Request(file_dir, data=None, headers={'User-Agent': 'whatever'})
				temp = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
			else:
				try:
					temp = json.loads(open(local_dir+info.file_dir.split('/')[-1]).read())
				except:
					req = urllib.request.Request(info.file_dir, data=None, headers={'User-Agent': 'whatever'})
					temp = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
			df = pd.DataFrame(temp, index=list(range(1,len(temp)+1)))
			df = df.assign(token=df.effect==2, long=df.effect.apply(lambda x: x == 3), 
						   star=df.effect==4, swing=df.effect.apply(lambda x: x in [11,13]))
			if i > 0:
				df['timing_sec'] = df['timing_sec'] + durations[i-1]
			df['tap'] = df.apply(lambda x: not (x.long or x.swing), axis=1)
			dfs.append(df.copy())
			self.note_number += len(df)
			durations.append((df.timing_sec + df.long*df.effect_value).max())

		df = pd.concat(dfs)
		df.index = list(range(1,len(df)+1))
		self.note_list, self.duration = df, durations[-1]
		# Compute end time for each note
		self.compute_stat()
	def __repr__(self):
		return '{0} {1}: attr={2}, duration={3}'.format(self.name, self.difficulty, self.attr, self.duration)
	def compute_stat(self):
		df = self.note_list.copy()
		df.timing_sec = df.timing_sec + df.effect_value * df.long
		df = df.sort_values(by='timing_sec', ascending=True)
		df.index = [i for i in range(1, len(df)+1)]
		# Compute all factors that matter scoring, under presumed perfect rate
		p, alpha, beta = self.perfect_rate, accuracy_factor['Perfect'], accuracy_factor['Great']
		df['judge_factor'] = df.long.apply(lambda x: ( alpha*p + beta*(1-p) )**(1+x) )
		df['note_factor'] = df.apply(lambda x: long_factor**x.long * swing_factor**x.swing, axis=1)
		df['combo_factor'] = [combo_factor(i) for i in range(1,len(df)+1)]
		df['total_factor'] = df.combo_factor * df.note_factor * df.judge_factor
		# Compute stats for each position
		note_stat = df.groupby(by='position')[['tap', 'long', 'swing', 'star', 'token']].sum().applymap(int)
		note_stat['note_factor'] = df.groupby(by='position')['note_factor'].sum()
		note_stat['total_factor'] = df.groupby(by='position')['total_factor'].sum()
		if len(note_stat) < 9:
			missing_pos = [x for x in range(1,10) if x not in note_stat.index]
			for pos in missing_pos:
				note_stat = note_stat.append(pd.DataFrame(0*note_stat.sum(), columns=[pos]).transpose())
			note_stat = note_stat.sort_index()
		note_stat = note_stat.append(pd.DataFrame(note_stat.sum(), columns=['total']).transpose())
		note_stat['weight'] = note_stat['total_factor'] / note_stat.loc['total','total_factor']
		# Save useful statistics as member variables
		self.summary = note_stat
		self.star_density = note_stat.loc['total','star'] / self.note_number

		self.note_type_dist = dict()
		self.note_type_dist['normal_density'] = note_stat.loc['total','tap'] / self.note_number
		self.note_type_dist['long_density'] = note_stat.loc['total','long'] / self.note_number
		self.note_type_dist['swing_density'] = note_stat.loc['total','swing'] / self.note_number

		self.average_bonus = note_stat.loc['total','total_factor']/self.note_number
		self.strength_per_pt_tap = (1/base_score_factor) / (note_stat.loc['total','total_factor']/self.note_number)
		self.pts_per_strength = base_score_factor * note_stat.loc['total','total_factor']
		self.combo_weight_fraction = self.summary.weight.values[-2::-1]