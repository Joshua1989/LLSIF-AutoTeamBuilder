# LLSIF-AutoTeamBuilder
Automatically build the optimal team according to given live and user profile

## Dependencies
Enviroment: Python3 & Jupyter notebook

Modules: `pandas, numpy, beautifulsoup4, json, sqlite3`

## Features
* Provide scrapper to collect icon image and live note list from from [Kirara](https://sif.kirara.ca/checklist), [ieb Stats site](http://stats.llsif.win/) and [LoveLive!查卡器](http://c.dash.moe/).
* Import user profile from tshark json packets or [ieb Stats site](http://stats.llsif.win/)
* Provide format converter for [LL组卡器](https://tieba.baidu.com/p/4986384618), [LL Helper](http://llhelper.duapp.com/), and [ieb Stats site](http://stats.llsif.win/)
* HTML view of all objects under Jupyter environment
* Customize selecting and sorting for user cards
* Built-in simulator to with comprehensive stats

## Documents
Notice most image and live resources are scraped after installation, the documents below are not displayed correctly in Github.

* Tutorial.ipynb: A general guide for how to use the module `llatb` and how to build optimal team
* doc folder: Advanded theoretic material and algorithm details.
