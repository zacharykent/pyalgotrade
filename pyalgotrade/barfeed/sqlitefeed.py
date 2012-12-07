# PyAlgoTrade
# 
# Copyright 2012 Gabriel Martin Becedillas Ruiz
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
.. moduleauthor:: Gabriel Martin Becedillas Ruiz <gabriel.becedillas@gmail.com>
"""

from pyalgotrade import barfeed
from pyalgotrade.barfeed import dbfeed
from pyalgotrade import bar
from pyalgotrade.utils import dt

import sqlite3
import os

class Database(dbfeed.Database):
	def __init__(self, dbFilePath):
		self.__instrumentIds = {}

		# If the file doesn't exist, we'll create it and initialize it.
		initialize = False
		if not os.path.exists(dbFilePath):
			initialize = True
		self.__connection = sqlite3.connect(dbFilePath)
		self.__connection.isolation_level = None # To do auto-commit
		if initialize:
			self.createSchema()

	def __findInstrumentId(self, instrument):
		cursor = self.__connection.cursor()
		sql = "select instrument_id from instrument where name = ?"
		cursor.execute(sql, [instrument])
		ret = cursor.fetchone()
		if ret != None:
			ret = ret[0]
		cursor.close()
		return ret

	def __addInstrument(self, instrument):
		ret =  self.__connection.execute("insert into instrument (name) values (?)", [instrument])
		return ret.lastrowid

	def __getOrCreateInstrument(self, instrument):
		# Try to get the instrument id from the cache.
		ret = self.__instrumentIds.get(instrument, None)
		if ret != None:
			return ret
		# If its not cached, get it from the db.
		ret = self.__findInstrumentId(instrument)
		# If its not in the db, add it.
		if ret == None:
			ret = self.__addInstrument(instrument)
		# Cache the id.
		self.__instrumentIds[instrument] = ret
		return ret

	def createSchema(self):
		self.__connection.execute("create table instrument ("
			+ "instrument_id integer primary key autoincrement"
			+ ", name text unique not null)")

		self.__connection.execute("create table bar ("
			+ "instrument_id integer references instrument (instrument_id)"
			+ ",frequency integer not null"
			+ ",timestamp integer not null"
			+ ",open real not null"
			+ ",high real not null"
			+ ",low real not null"
			+ ",close real not null"
			+ ",volume real not null"
			+ ",adj_close real"
			+ ",primary key (instrument_id, frequency, timestamp))" )

	def addBar(self, instrument, bar, frequency):
		instrumentId = self.__getOrCreateInstrument(instrument)
		timeStamp = dt.datetime_to_timestamp(bar.getDateTime())

		try:
			sql = "insert into bar (instrument_id, frequency, timestamp, open, high, low, close, volume, adj_close) values (?, ?, ?, ?, ?, ?, ?, ?, ?)"
			params = [instrumentId, frequency, timeStamp, bar.getOpen(), bar.getHigh(), bar.getLow(), bar.getClose(), bar.getVolume(), bar.getAdjClose()]
			self.__connection.execute(sql, params)
		except sqlite3.IntegrityError:
			sql = "update bar set open = ?, high = ?, low = ?, close = ?, volume = ?, adj_close = ?" \
					" where instrument_id = ? and frequency = ? and timestamp = ?"
			params = [bar.getOpen(), bar.getHigh(), bar.getLow(), bar.getClose(), bar.getVolume(), bar.getAdjClose(), instrumentId, frequency, timeStamp]
			self.__connection.execute(sql, params)

	def getBars(self, instrument, frequency, fromDateTime = None, toDateTime = None):
		sql = "select bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume, bar.adj_close" \
				" from bar join instrument on (bar.instrument_id = instrument.instrument_id)" \
				" where instrument.name = ? and bar.frequency = ?"
		args = [instrument, frequency]

		if fromDateTime != None:
			sql += " and bar.timestamp >= ?"
			args.append(dt.datetime_to_timestamp(fromDateTime))
		if toDateTime != None:
			sql += " and bar.timestamp <= ?"
			args.append(dt.datetime_to_timestamp(toDateTime))

		sql += " order by bar.timestamp asc"
		cursor = self.__connection.cursor()
		cursor.execute(sql, args)
		ret = []
		for row in cursor:
			ret.append(bar.Bar(dt.timestamp_to_datetime(row[0]), row[1], row[2], row[3], row[4], row[5], row[6]))
		cursor.close()
		return ret

class Feed(barfeed.InMemoryBarFeed):
	def __init__(self, dbFilePath):
		barfeed.InMemoryBarFeed.__init__(self)
		self.__db = Database(dbFilePath)

	def loadBars(self, instrument, frequency, fromDateTime = None, toDateTime = None):
		bars = self.__db.getBars(instrument, frequency, fromDateTime, toDateTime)
		self.addBarsFromSequence(instrument, bars)
