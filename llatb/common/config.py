import os
import os 
from pathlib import Path
from llatb.common.global_var import gem_skill_dict, gem_skill_id_rev_dict

root = os.path.dirname(os.path.realpath(__file__)).split('llatb')[0]

# Comprehensive card information
card_archive_dir = root+'assets/data_base.json'
# Comprehensive live basic information
live_archive_dir = root+'assets/live_data_base.json'
# unit_id and unit_number correspondence
unit_db_dir = root+'assets/unit.db_'
unit_db_download_url = 'https://r.llsif.win/db/unit/unit.db_'
live_db_dir = root+'assets/live.db_'
live_db_download_url = 'https://r.llsif.win/db/live/live.db_'

# Path function for saving downloaded resources and HTML image embedding
def icon_path(card_id, idolized):
	return 'http://gitcdn.xyz/repo/iebb/SIFStatic/master/icon/{0}/{1}.png'.format('rankup' if idolized else 'normal', card_id)
def gem_path(name):
	if name == 'empty':
		return 'https://r.llsif.win/assets/image/ui/common/com_etc_66.png'
	elif name == 'placeholder':
		return 'https://r.llsif.win/assets/image/ui/common/com_etc_68.png'
	elif name == 'void':
		return 'https://r.llsif.win/assets/image/ui/live/l_etc_xxx.png'
	else:
		cost, idx = gem_skill_dict[name]['cost'], gem_skill_id_rev_dict[name]
		return 'http://my.llsif.win/images/sis/sis{0}_{1}.png'.format(str(idx).zfill(3), str(cost).zfill(2))
def misc_path(name):
	url_dict = {
		'smile':'http://c.dash.moe/static/images/smile.png',
		'pure':'http://c.dash.moe/static/images/pure.png',
		'cool':'http://c.dash.moe/static/images/cool.png',
		'empty':'https://r.llsif.win/assets/image/ui/live/l_etc_xxx.png',
		'Weak Judge':'http://c.dash.moe/static/images/skillsyo.png',
		'Strong Judge':'http://c.dash.moe/static/images/skilldai.png',
		'Score Up':'http://c.dash.moe/static/images/skillscoreup.png',
		'Stamina Restore':'http://c.dash.moe/static/images/skilllifeup.png',
		'bond':'https://r.llsif.win/assets/image/ui/common/com_etc_251.png',
		'level':'https://r.llsif.win/assets/image/ui/common/com_etc_252.png',
		'idolized':'https://r.llsif.win/assets/image/ui/common/com_etc_250.png',
		'hp':'https://r.llsif.win/assets/image/ui/common/com_icon_04.png',
		'Smile Note':'http://c.dash.moe/asset/assets/flash/ui/live/img/ef_315_notes_0101.png',
		'Pure Note':'http://c.dash.moe/asset/assets/flash/ui/live/img/ef_315_notes_0102.png',
		'Cool Note':'http://c.dash.moe/asset/assets/flash/ui/live/img/ef_315_notes_0103.png',
		'Smile Swing':'http://c.dash.moe/asset/assets/flash/ui/live/img/ef_315_notes_0111.png',
		'Pure Swing':'http://c.dash.moe/asset/assets/flash/ui/live/img/ef_315_notes_0112.png',
		'Cool Swing':'http://c.dash.moe/asset/assets/flash/ui/live/img/ef_315_notes_0113.png',
		'long':'http://c.dash.moe/asset/assets/flash/ui/live/img/ef_326_002.png',
		'star':'http://c.dash.moe/asset/assets/flash/ui/live/img/ef_315_effect_0004.png',
		'1st-year':'https://r.llsif.win/assets/image/event/mission/ms_m_type_01.png',
		'2nd-year':'https://r.llsif.win/assets/image/event/mission/ms_m_type_02.png',
		'3rd-year':'https://r.llsif.win/assets/image/event/mission/ms_m_type_03.png',
		'Printemps':'https://r.llsif.win/assets/image/event/mission/ms_m_type_04.png',
		'lily white':'https://r.llsif.win/assets/image/event/mission/ms_m_type_05.png',
		'BiBi':'https://r.llsif.win/assets/image/event/mission/ms_m_type_06.png',
		'CYaRon！':'https://r.llsif.win/assets/image/event/mission/ms_m_type_07.png',
		'AZALEA':'https://r.llsif.win/assets/image/event/mission/ms_m_type_08.png',
		'Guilty Kiss':'https://r.llsif.win/assets/image/event/mission/ms_m_type_09.png',
		"μ's":'https://r.llsif.win/assets/image/event/mission/ms_m_type_10.png',
		'Aqours':'https://r.llsif.win/assets/image/event/mission/ms_m_type_11.png'
	}
	return url_dict.get(name,name)
def cover_path(sub_dir):
	return 'https://r.llsif.win/{0}'.format(sub_dir)
def live_path(sub_dir):
	return 'https://r.llsif.win/livejson/{0}'.format(sub_dir)

if not Path(card_archive_dir).exists():
	print('{0} does not exist'.format(card_archive_dir))
if not Path(live_archive_dir).exists():
	print('{0} does not exist'.format(live_archive_dir))
if not Path(unit_db_dir).exists():
	print('{0} does not exist'.format(unit_db_dir))

html_template = '''
<!DOCTYPE html>
<html>

<head>
    <style>
    table {{
        margin-left: 0px;
        margin-right: auto;
        border: none;
        border-collapse: collapse;
        border-spacing: 0;
        color: @rendered_html_border_color;
        font-size: 12px;
        table-layout: fixed;
    }}
    
    th {{
	    white-space: nowrap;
	}}

	td {{
	    white-space: nowrap;
	}}
    
    th {{
        font-weight: bold;
    }}
    
    tbody tr:nth-child(odd) {{
        background: #f5f5f5;
    }}
    
    * + table {{
        margin-top: 1em;
    }}
    
    p {{
        text-align: center;
    }}
    
    img {{
        display: block;
        margin-left: auto;
        margin-right: auto;
    }}
    </style>
</head>
<body>
    {0} 
</body>

</html>
'''