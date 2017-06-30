import numpy as np
import pandas as pd
import json
from llatb.common.config import live_archive_dir, live_path
from llatb.common.global_var import *
from IPython.display import HTML

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
	def __init__(self, name, difficulty, perfect_rate=0.95):
		try:
			info = live_basic_data[live_basic_data.apply(lambda x: x['name']==name and x['diff_level']==difficulty, axis=1)].iloc[0]
		except:
			print('Live data of {0} {1} not found!'.format(name, difficulty))
			raise
		self.name, self.difficulty = name, difficulty
		self.group, self.attr = info.group, info.attr
		temp = json.loads(open(live_path(info.file_dir)).read())
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
	def __init__(self, name, difficulty='Master', setting=default_setting):
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
		self.perfect_rate = param['perfect_rate']
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