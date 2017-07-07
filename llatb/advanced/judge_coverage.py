import math
import numpy as np
import matplotlib.pyplot as plt
from llatb.common.global_var import combo_factor

Offset = [4.5, 4, 3.625, 3.25, 2.875, 2.5, 2.25, 2, 1.75, 1.5]
Speed = [1.8, 1.6, 1.45, 1.3, 1.15, 1, 0.9, 0.8, 0.7, 0.6]
Perfect = [0.072, 0.064, 0.058, 0.052, 0.046, 0.04, 0.036, 0.032, 0.032, 0.032]
Great = [0.18, 0.16, 0.145, 0.13, 0.115, 0.1, 0.09, 0.08, 0.08, 0.08]
Good = [0.288, 0.256, 0.232, 0.208, 0.184, 0.16, 0.144, 0.128, 0.128, 0.128]
Bad = [0.504, 0.448, 0.406, 0.364, 0.322, 0.28, 0.252, 0.224, 0.224, 0.224]
diff_speed_dict = {'Easy':2, 'Normal':4, 'Hard':6, 'Expert':8, 'Master':9}
field_names = ['offset', 'speed', 'perfect', 'great', 'good', 'bad']
Speed_info = {s:dict() for s in range(1,11)}
for s, item in enumerate(zip(Offset, Speed, Perfect, Great, Good, Bad), 1):
	for i, field in enumerate(field_names):
		Speed_info[s][field] = item[i]

class CoverageCalculator:
	def __init__(self, live, offset=0, speed=None):
		self.live = live
		self.speed = speed if speed is not None else diff_speed_dict[live.difficulty]
		self.SI = Speed_info[self.speed]
		self.Map_note = live.note_list.apply(lambda x: round(1000*(x.timing_sec-self.SI['speed'])), axis=1).values
		self.Map_beat = live.note_list.apply(lambda x: round(1000*(x.timing_sec+x.long*x.effect_value+self.SI['bad'])-offset*self.SI['offset']), axis=1).values
		self.Map_CTrigger = live.note_list.apply(lambda x: round(1000*(x.timing_sec+x.long*x.effect_value)-offset*self.SI['offset']), axis=1).values
	def N_calc(self, n, p, td):
		TimeAxis = np.ones(int(self.Map_beat[-1]+2*td*1000))
		num_period = math.floor(self.live.note_number/n)
		intervals = []
		for i in range(num_period):
			# Compute the first state of current period
			start = self.Map_note[(i+1)*n-1]
			curr_period = [{'start':start, 'end':start+td*1000, 'prob':p*TimeAxis[start-2]}]
			# Compute rest states of current period
			temp = []
			for l in range(1,i+1):
				for intv in intervals[i-l]:
					if intv['end'] >= curr_period[0]['start'] and intv['start'] <= curr_period[0]['start']:
						x = np.all([intervals[i-y][0]['start'] < intv['start'] for y in range(1,l)])
						temp.append({'start':intv['end'], 'end':intv['end']+td*1000, 'prob':p*intv['prob']*x})
			# Combine overlapped states
			l = 0
			while l < len(temp):
				while l < len(temp):
					if temp[l]['start'] != -1:
						curr_period.append(temp[l].copy())
						break
					l += 1
				for intv in temp[l+1:]:
					if intv['start'] == temp[l]['start']:
						intv['start'] = -1
						curr_period[-1]['prob'] += intv['prob']
				l += 1
			# Export result to time axis
			for intv in curr_period:
				TimeAxis[int(intv['start']):int(intv['end'])] -= intv['prob']
			intervals.append(curr_period)
		return 1-TimeAxis

	def T_calc(self, t, p, td):
		TimeAxis = np.ones(int(self.Map_beat[-1]+td*1000))
		# Since the discharge time and effect time are multiply of 0.5s
		k = math.ceil(self.Map_beat[-1]/500)
		f, g = np.zeros(k), np.zeros(k)
		g[0], intervals = 1, []
		for i in range(2*t, k):
			f[i], g[i] = p * g[int(i-2*t)], f[int(i-2*td)] + (1-p) * g[int(i-2*t)]
			if f[i] > 0:
				intervals.append({'start': i*500,'end': (i+2*td)*500,'prob': f[i]})
		for intv in intervals:
			TimeAxis[int(intv['start']):int(intv['end'])] -= intv['prob']
		return 1-TimeAxis

	def C_calc(self, c, p, td):
		TimeAxis = np.ones(int(self.Map_beat[-1])+2*td*1000)
		num_period = math.floor(self.live.note_number/c)
		intervals = []
		for i in range(num_period):
			# Compute the first state of current period
			start = self.Map_CTrigger[(i+1)*c-1]
			curr_period = [{'start':start, 'end':start+td*1000, 'prob':p*TimeAxis[start-2]}]
			# Compute rest states of current period
			temp = []
			for l in range(1,i+1):
				for intv in intervals[i-l]:
					if intv['end'] >= curr_period[0]['start'] and intv['start'] <= curr_period[0]['start']:
						x = np.all([intervals[i-y][0]['start'] < intv['start'] for y in range(1,l)])
						temp.append({'start':intv['end'], 'end':intv['end']+td*1000, 'prob':p*intv['prob']*x})
			# Combine overlapped states
			l = 0
			while l < len(temp):
				while l < len(temp):
					if temp[l]['start'] != -1:
						curr_period.append(temp[l].copy())
						break
					l += 1
				for intv in temp[l+1:]:
					if intv['start'] == temp[l]['start']:
						intv['start'] = -1
						curr_period[-1]['prob'] += intv['prob']
				l += 1
			# Export result to time axis
			for intv in curr_period:
				TimeAxis[int(intv['start']):int(intv['end'])] -= intv['prob']
			intervals.append(curr_period)
		return 1-TimeAxis

	def compute_coverage(self, card, plot=False):
		if card.skill is None or card.skill.effect_type not in ['Strong Judge', 'Weak Judge']: return 0
		skill = card.skill
		if skill.trigger_type == 'Note':
			TimeAxis = self.N_calc(skill.trigger_count, skill.odds/100, skill.reward)
		elif skill.trigger_type == 'Time':
			TimeAxis = self.T_calc(skill.trigger_count, skill.odds/100, skill.reward)
		elif skill.trigger_type == 'Combo':
			TimeAxis = self.C_calc(skill.trigger_count, skill.odds/100, skill.reward)

		TempCoverage = np.zeros(self.live.note_number)
		for i in range(self.live.note_number):
			if self.live.note_list.iloc[i]['long']:
				a1, a2 = self.Map_CTrigger[i] - 1000*self.SI['bad'], self.Map_CTrigger[i] + 1000*self.SI['bad']
			else:
				a1, a2 = self.Map_CTrigger[i] - 1000*self.SI['good'], self.Map_CTrigger[i] + 1000*self.SI['good']
			TempCoverage[i] = TimeAxis[int(a1):int(a2)].sum() / (a2-a1)

		CR = TempCoverage.mean()
		if plot:
			plt.figure(figsize=(12,4))
			t = np.arange(self.Map_beat[-1]) / 1000
			plt.plot(t, TimeAxis[:len(t)])
			plt.title('{0} triggered, ({1},{2}%,{3}), total note coverage {4:.2f}%'.format(skill.trigger_type, skill.trigger_count, skill.odds, skill.reward, 100*CR))
		return CR
