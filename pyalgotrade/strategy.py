# PyAlgoTrade
# 
# Copyright 2011 Gabriel Martin Becedillas Ruiz
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

import broker
from broker import backtesting
import utils
import observer

class Position:
	"""Base class for positions. 

	:param entryOrder: The order used to enter the position.
	:type entryOrder: :class:`pyalgotrade.broker.Order`
	:param goodTillCanceled: True if orders should be set as good till canceled.
	:type goodTillCanceled: boolean.

	.. note::
		This is a base class and should not be used directly.
	"""

	def __init__(self, entryOrder, goodTillCanceled):
		self.__entryOrder = entryOrder
		self.__exitOrder = None
		self.__exitOnSessionClose = False
		self.__goodTillCanceled = goodTillCanceled
		entryOrder.setGoodTillCanceled(goodTillCanceled)

	def getGoodTillCanceled(self):
		return self.__goodTillCanceled

	def setExitOnSessionClose(self, exitOnSessionClose):
		"""Set to True to automatically place the exit order in the last bar for the session. Only useful for intraday trading."""
		self.__exitOnSessionClose = exitOnSessionClose

	def getExitOnSessionClose(self):
		"""Returns True if an order to exit the position should be automatically placed."""
		return self.__exitOnSessionClose

	def getEntryOrder(self):
		"""Returns the :class:`pyalgotrade.broker.Order` used to enter the position."""
		return self.__entryOrder

	def setExitOrder(self, exitOrder):
		self.__exitOrder = exitOrder

	def getExitOrder(self):
		"""Returns the :class:`pyalgotrade.broker.Order` used to exit the position. If this position hasn't been closed yet, None is returned."""
		return self.__exitOrder

	def getInstrument(self):
		"""Returns the instrument used for this position."""
		return self.__entryOrder.getInstrument()

	def getQuantity(self):
		"""Returns the number of shares used to enter this position."""
		return self.__entryOrder.getQuantity()

	def close(self, limitPrice, stopPrice, broker_):
		assert(self.getExitOrder() == None or self.getExitOrder().isCanceled())
		closeOrder = self.buildExitOrder(limitPrice, stopPrice)
		broker_.placeOrder(closeOrder)
		self.setExitOrder(closeOrder)

	def checkExitOnSessionClose(self, bars, broker_):
		ret = None
		try:
			if self.__exitOnSessionClose and self.__exitOrder == None and bars.getBar(self.getInstrument()).getBarsTillSessionClose() == 1:
				assert(self.getEntryOrder() != None)
				ret = self.buildExitOnSessionCloseOrder()
				ret = broker_.createExecuteIfFilled(ret, self.getEntryOrder())
				broker_.placeOrder(ret)
				self.setExitOrder(ret)
		except KeyError:
			pass

		return ret

	def getResult(self):
		"""Returns the ratio between the order prices. **It doesn't include commisions**."""
		if not self.getEntryOrder().isFilled():
			raise Exception("Position not opened yet")
		if self.getExitOrder() == None or not self.getExitOrder().isFilled():
			raise Exception("Position not closed yet")
		return self.getResultImpl()

	def getResultImpl(self):
		raise Exception("Not implemented")

	def getNetProfit(self):
		"""Returns the difference between the order prices. **It does include commisions**."""
		if not self.getEntryOrder().isFilled():
			raise Exception("Position not opened yet")
		if self.getExitOrder() == None or not self.getExitOrder().isFilled():
			raise Exception("Position not closed yet")
		return self.getNetProfitImpl()

	def getNetProfitImpl(self):
		raise Exception("Not implemented")

	def buildExitOrder(self, limitPrice, stopPrice):
		raise Exception("Not implemented")

	def buildExitOnSessionCloseOrder(self):
		raise Exception("Not implemented")

# This class is reponsible for order management in long positions.
class LongPosition(Position):
	def __init__(self, broker_, instrument, limitPrice, stopPrice, quantity, goodTillCanceled):
		self.__broker = broker_
		if limitPrice == None and stopPrice == None:
			entryOrder = self.__broker.createMarketOrder(broker.Order.Action.BUY, instrument, quantity, False)
		elif limitPrice != None and stopPrice == None:
			entryOrder = self.__broker.createLimitOrder(broker.Order.Action.BUY, instrument, limitPrice, quantity)
		elif limitPrice == None and stopPrice != None:
			entryOrder = self.__broker.createStopOrder(broker.Order.Action.BUY, instrument, stopPrice, quantity)
		elif limitPrice != None and stopPrice != None:
			entryOrder = self.__broker.createStopLimitOrder(broker.Order.Action.BUY, instrument, stopPrice, limitPrice, quantity)
		else:
			assert(False)

		Position.__init__(self, entryOrder, goodTillCanceled)
		self.__broker.placeOrder(entryOrder)

	def getResultImpl(self):
		return utils.get_change_percentage(self.getExitOrder().getExecutionInfo().getPrice(), self.getEntryOrder().getExecutionInfo().getPrice())

	def getNetProfitImpl(self):
		ret = self.getExitOrder().getExecutionInfo().getPrice() - self.getEntryOrder().getExecutionInfo().getPrice()
		ret -= self.getEntryOrder().getExecutionInfo().getCommission()
		ret -= self.getExitOrder().getExecutionInfo().getCommission()
		return ret

	def buildExitOrder(self, limitPrice, stopPrice):
		if limitPrice == None and stopPrice == None:
			ret = self.__broker.createMarketOrder(broker.Order.Action.SELL, self.getInstrument(), self.getQuantity(), False)
		elif limitPrice != None and stopPrice == None:
			ret = self.__broker.createLimitOrder(broker.Order.Action.SELL, self.getInstrument(), limitPrice, self.getQuantity())
		elif limitPrice == None and stopPrice != None:
			ret = self.__broker.createStopOrder(broker.Order.Action.SELL, self.getInstrument(), stopPrice, self.getQuantity())
		elif limitPrice != None and stopPrice != None:
			ret = self.__broker.createStopLimitOrder(broker.Order.Action.SELL, self.getInstrument(), stopPrice, limitPrice, self.getQuantity())
		else:
			assert(False)

		ret.setGoodTillCanceled(self.getGoodTillCanceled())
		return ret

	def buildExitOnSessionCloseOrder(self):
		ret = self.__broker.createMarketOrder(broker.Order.Action.SELL, self.getInstrument(), self.getQuantity(), True)
		ret.setGoodTillCanceled(self.getGoodTillCanceled())
		return ret

# This class is reponsible for order management in short positions.
class ShortPosition(Position):
	def __init__(self, broker_, instrument, limitPrice, stopPrice, quantity, goodTillCanceled):
		self.__broker = broker_
		if limitPrice == None and stopPrice == None:
			entryOrder = self.__broker.createMarketOrder(broker.Order.Action.SELL_SHORT, instrument, quantity, False)
		elif limitPrice != None and stopPrice == None:
			entryOrder = self.__broker.createLimitOrder(broker.Order.Action.SELL_SHORT, instrument, limitPrice, quantity)
		elif limitPrice == None and stopPrice != None:
			entryOrder = self.__broker.createStopOrder(broker.Order.Action.SELL_SHORT, instrument, stopPrice, quantity)
		elif limitPrice != None and stopPrice != None:
			entryOrder = self.__broker.createStopLimitOrder(broker.Order.Action.SELL_SHORT, instrument, stopPrice, limitPrice, quantity)
		else:
			assert(False)

		Position.__init__(self, entryOrder, goodTillCanceled)
		self.__broker.placeOrder(entryOrder)

	def getResultImpl(self):
		return utils.get_change_percentage(self.getEntryOrder().getExecutionInfo().getPrice(), self.getExitOrder().getExecutionInfo().getPrice())

	def getNetProfitImpl(self):
		ret = self.getEntryOrder().getExecutionInfo().getPrice() - self.getExitOrder().getExecutionInfo().getPrice()
		ret -= self.getEntryOrder().getExecutionInfo().getCommission()
		ret -= self.getExitOrder().getExecutionInfo().getCommission()
		return ret

	def buildExitOrder(self, limitPrice, stopPrice):
		if limitPrice == None and stopPrice == None:
			ret = self.__broker.createMarketOrder(broker.Order.Action.BUY_TO_COVER, self.getInstrument(), self.getQuantity(), False)
		elif limitPrice != None and stopPrice == None:
			ret = self.__broker.createLimitOrder(broker.Order.Action.BUY_TO_COVER, self.getInstrument(), limitPrice, self.getQuantity())
		elif limitPrice == None and stopPrice != None:
			ret = self.__broker.createStopOrder(broker.Order.Action.BUY_TO_COVER, self.getInstrument(), stopPrice, self.getQuantity())
		elif limitPrice != None and stopPrice != None:
			ret = self.__broker.createStopLimitOrder(broker.Order.Action.BUY_TO_COVER, self.getInstrument(), stopPrice, limitPrice, self.getQuantity())
		else:
			assert(False)

		ret.setGoodTillCanceled(self.getGoodTillCanceled())
		return ret

	def buildExitOnSessionCloseOrder(self):
		ret = self.__broker.createMarketOrder(broker.Order.Action.BUY_TO_COVER, self.getInstrument(), self.getQuantity(), True)
		ret.setGoodTillCanceled(self.getGoodTillCanceled())
		return ret

class Strategy:
	"""Base class for strategies. 

	:param barFeed: The bar feed to use to backtest the strategy.
	:type barFeed: :class:`pyalgotrade.barfeed.BarFeed`.
	:param cash: The amount of cash available.
	:type cash: int/float.
	:param broker_: Broker to use. If not specified the default broker (:class:`pyalgotrade.broker.backtesting.Broker`) 
					will be created.
	:type broker_: :class:`pyalgotrade.broker.Broker`.

	.. note::
		This is a base class and should not be used directly.
	"""

	def __init__(self, barFeed, cash = 0, broker_ = None):
		self.__feed = barFeed
		self.__activePositions = {}
		self.__orderToPosition = {}
		self.__barsProcessedEvent = observer.Event()

		if broker_ == None:
			# When doing backtesting (broker_ == None), the broker should subscribe to barFeed events before the strategy.
			# This is to avoid executing orders placed in the current tick.
			self.__broker = broker.backtesting.Broker(cash, barFeed)
		else:
			self.__broker = broker_
		self.__broker.getOrderUpdatedEvent().subscribe(self.__onOrderUpdate)

	def getResult(self):
		ret = 0
		bars = self.__feed.getLastBars()
		if bars != None:
			ret = self.getBroker().getValue(bars)
		return ret

	def getBarsProcessedEvent(self):
		return self.__barsProcessedEvent

	def __registerOrder(self, position, order):
		try:
			orders = self.__activePositions[position]
		except KeyError:
			orders = set()
			self.__activePositions[position] = orders

		if order.isAccepted():
			self.__orderToPosition[order] = position
			orders.add(order)

	def __unregisterOrder(self, position, order):
		del self.__orderToPosition[order]

		orders = self.__activePositions[position]
		orders.remove(order)
		if len(orders) == 0:
			del self.__activePositions[position]

	def __registerActivePosition(self, position):
		for order in [position.getEntryOrder(), position.getExitOrder()]:
			if order and order.isAccepted():
				self.__registerOrder(position, order)

	def getFeed(self):
		"""Returns the :class:`pyalgotrade.barfeed.BarFeed` that this strategy is using."""
		return self.__feed

	def getCurrentDateTime(self):
		"""Returns the :class:`datetime.datetime` for the current :class:`pyalgotrade.bar.Bar`."""
		ret = None
		bars = self.__feed.getLastBars()
		if bars:
			ret = bars.getDateTime()
		return ret

	def getBroker(self):
		"""Returns the :class:`pyalgotrade.broker.Broker` used to handle order executions."""
		return self.__broker

	def enterLong(self, instrument, quantity, goodTillCanceled = False):
		"""Generates a buy :class:`pyalgotrade.broker.MarketOrder` to enter a long position.

		:param instrument: Instrument identifier.
		:type instrument: string.
		:param quantity: Entry order quantity.
		:type quantity: int.
		:param goodTillCanceled: True if the entry/exit orders are good till canceled. If False then orders get automatically canceled when session closes.
		:type goodTillCanceled: boolean.
		:rtype: The :class:`Position` entered.
		"""

		ret = LongPosition(self.__broker, instrument, None, None, quantity, goodTillCanceled)
		self.__registerActivePosition(ret)
		return ret

	def enterShort(self, instrument, quantity, goodTillCanceled = False):
		"""Generates a sell short :class:`pyalgotrade.broker.MarketOrder` to enter a short position.

		:param instrument: Instrument identifier.
		:type instrument: string.
		:param quantity: Entry order quantity.
		:type quantity: int.
		:param goodTillCanceled: True if the entry/exit orders are good till canceled. If False then orders get automatically canceled when session closes.
		:type goodTillCanceled: boolean.
		:rtype: The :class:`Position` entered.
		"""

		ret = ShortPosition(self.__broker, instrument, None, None, quantity, goodTillCanceled)
		self.__registerActivePosition(ret)
		return ret

	def enterLongLimit(self, instrument, limitPrice, quantity, goodTillCanceled = False):
		"""Generates a buy :class:`pyalgotrade.broker.LimitOrder` to enter a long position.

		:param instrument: Instrument identifier.
		:type instrument: string.
		:param limitPrice: Limit price.
		:type limitPrice: float.
		:param quantity: Entry order quantity.
		:type quantity: int.
		:param goodTillCanceled: True if the entry/exit orders are good till canceled. If False then orders get automatically canceled when session closes.
		:type goodTillCanceled: boolean.
		:rtype: The :class:`Position` entered.
		"""

		ret = LongPosition(self.__broker, instrument, limitPrice, None, quantity, goodTillCanceled)
		self.__registerActivePosition(ret)
		return ret

	def enterShortLimit(self, instrument, limitPrice, quantity, goodTillCanceled = False):
		"""Generates a sell short :class:`pyalgotrade.broker.LimitOrder` to enter a short position.

		:param instrument: Instrument identifier.
		:type instrument: string.
		:param limitPrice: Limit price.
		:type limitPrice: float.
		:param quantity: Entry order quantity.
		:type quantity: int.
		:param goodTillCanceled: True if the entry/exit orders are good till canceled. If False then orders get automatically canceled when session closes.
		:type goodTillCanceled: boolean.
		:rtype: The :class:`Position` entered.
		"""

		ret = ShortPosition(self.__broker, instrument, limitPrice, None, quantity, goodTillCanceled)
		self.__registerActivePosition(ret)
		return ret
	
	def enterLongStop(self, instrument, stopPrice, quantity, goodTillCanceled = False):
		"""Generates a buy :class:`pyalgotrade.broker.StopOrder` to enter a long position.

		:param instrument: Instrument identifier.
		:type instrument: string.
		:param stopPrice: Stop price.
		:type stopPrice: float.
		:param quantity: Entry order quantity.
		:type quantity: int.
		:param goodTillCanceled: True if the entry/exit orders are good till canceled. If False then orders get automatically canceled when session closes.
		:type goodTillCanceled: boolean.
		:rtype: The :class:`Position` entered.
		"""

		ret = LongPosition(self.__broker, instrument, None, stopPrice, quantity, goodTillCanceled)
		self.__registerActivePosition(ret)
		return ret

	def enterShortStop(self, instrument, stopPrice, quantity, goodTillCanceled = False):
		"""Generates a sell short :class:`pyalgotrade.broker.StopOrder` to enter a short position.

		:param instrument: Instrument identifier.
		:type instrument: string.
		:param stopPrice: Stop price.
		:type stopPrice: float.
		:param quantity: Entry order quantity.
		:type quantity: int.
		:param goodTillCanceled: True if the entry/exit orders are good till canceled. If False then orders get automatically canceled when session closes.
		:type goodTillCanceled: boolean.
		:rtype: The :class:`Position` entered.
		"""

		ret = ShortPosition(self.__broker, instrument, None, stopPrice, quantity, goodTillCanceled)
		self.__registerActivePosition(ret)
		return ret

	def enterLongStopLimit(self, instrument, limitPrice, stopPrice, quantity, goodTillCanceled = False):
		"""Generates a buy :class:`pyalgotrade.broker.StopLimitOrder` order to enter a long position.

		:param instrument: Instrument identifier.
		:type instrument: string.
		:param limitPrice: Limit price.
		:type limitPrice: float.
		:param stopPrice: Stop price.
		:type stopPrice: float.
		:param quantity: Entry order quantity.
		:type quantity: int.
		:param goodTillCanceled: True if the entry/exit orders are good till canceled. If False then orders get automatically canceled when session closes.
		:type goodTillCanceled: boolean.
		:rtype: The :class:`Position` entered.
		"""

		ret = LongPosition(self.__broker, instrument, limitPrice, stopPrice, quantity, goodTillCanceled)
		self.__registerActivePosition(ret)
		return ret

	def enterShortStopLimit(self, instrument, limitPrice, stopPrice, quantity, goodTillCanceled = False):
		"""Generates a sell short :class:`pyalgotrade.broker.StopLimitOrder` order to enter a short position.

		:param instrument: Instrument identifier.
		:type instrument: string.
		:param limitPrice: Limit price.
		:type limitPrice: float.
		:param stopPrice: The Stop price.
		:type stopPrice: float.
		:param quantity: Entry order quantity.
		:type quantity: int.
		:param goodTillCanceled: True if the entry/exit orders are good till canceled. If False then orders get automatically canceled when session closes.
		:type goodTillCanceled: boolean.
		:rtype: The :class:`Position` entered.
		"""

		ret = ShortPosition(self.__broker, instrument, limitPrice, stopPrice, quantity, goodTillCanceled)
		self.__registerActivePosition(ret)
		return ret

	def exitPosition(self, position, limitPrice = None, stopPrice = None):
		"""Generates the exit order for the position.

		:param position: A position returned by any of the enterLongXXX or enterShortXXX methods.
		:type position: :class:`Position`.
		:param limitPrice: The limit price.
		:type limitPrice: float.
		:param stopPrice: The stop price.
		:type stopPrice: float.

		.. note::
			* If limitPrice is not set and stopPrice is not set, then a :class:`pyalgotrade.broker.MarketOrder` is used to exit the position.
			* If limitPrice is set and stopPrice is not set, then a :class:`pyalgotrade.broker.LimitOrder` is used to exit the position.
			* If limitPrice is not set and stopPrice is set, then a :class:`pyalgotrade.broker.StopOrder` is used to exit the position.
			* If limitPrice is set and stopPrice is set, then a :class:`pyalgotrade.broker.StopLimitOrder` is used to exit the position.
		"""

		if	position.getExitOrder() != None and \
			(position.getExitOrder().isFilled() or position.getExitOrder().isAccepted()):
			# The position is already closed or the exit order execution is still pending.
			return

		# Before exiting a position, the entry order must have been filled.
		if position.getEntryOrder().isFilled():
			position.close(limitPrice, stopPrice, self.__broker)
			self.__registerActivePosition(position)
		else: # If the entry was not filled, cancel it.
			position.getEntryOrder().cancel()

	def onEnterOk(self, position):
		"""Override (optional) to get notified when the order submitted to enter a position was filled. The default implementation is empty.

		:param position: A position returned by any of the enterLongXXX or enterShortXXX methods.
		:type position: :class:`Position`.
		"""
		pass

	def onEnterCanceled(self, position):
		"""Override (optional) to get notified when the order submitted to enter a position was canceled. The default implementation is empty.

		:param position: A position returned by any of the enterLongXXX or enterShortXXX methods.
		:type position: :class:`Position`.
		"""
		pass

	# Called when the exit order for a position was filled.
	def onExitOk(self, position):
		"""Override (optional) to get notified when the order submitted to exit a position was filled. The default implementation is empty.

		:param position: A position returned by any of the enterLongXXX or enterShortXXX methods.
		:type position: :class:`Position`.
		"""
		pass

	# Called when the exit order for a position was canceled.
	def onExitCanceled(self, position):
		"""Override (optional) to get notified when the order submitted to exit a position was canceled. The default implementation is empty.

		:param position: A position returned by any of the enterLongXXX or enterShortXXX methods.
		:type position: :class:`Position`.
		"""
		pass

	"""Base class for strategies. """
	def onStart(self):
		"""Override (optional) to get notified when the strategy starts executing. The default implementation is empty. """
		pass

	def onFinish(self, bars):
		"""Override (optional) to get notified when the strategy finished executing. The default implementation is empty.

		:param bars: The latest bars processed.
		:type bars: :class:`pyalgotrade.bar.Bars`.
		"""
		pass

	def onBars(self, bars):
		"""Override (mandatory) to get notified when new bars are available. The default implementation raises an Exception.

		**This is the method to override to enter your trading logic and enter/exit positions**.

		:param bars: The current bars.
		:type bars: :class:`pyalgotrade.bar.Bars`.
		"""
		raise Exception("Not implemented")

	def __onOrderUpdate(self, broker_, order):
		position = self.__orderToPosition[order]
		if position.getEntryOrder() == order:
			if order.isFilled():
				self.onEnterOk(position)
			elif order.isCanceled():
				self.__unregisterOrder(position, order)
				self.onEnterCanceled(position)
			else:
				assert(False)
		elif position.getExitOrder() == order:
			if order.isFilled():
				self.__unregisterOrder(position, order)
				self.onExitOk(position)
			elif order.isCanceled():
				self.__unregisterOrder(position, order)
				self.onExitCanceled(position)
			else:
				assert(False)
		else:
			assert(False)

	def __checkExitOnSessionClose(self, bars):
		for position in self.__activePositions.keys():
			order = position.checkExitOnSessionClose(bars, self.getBroker())
			if order:
				self.__registerOrder(position, order)

	def __onBars(self, bars):
		# THE ORDER HERE IS VERY IMPORTANT

		# 1: Let the strategy process current bars and place orders.
		self.onBars(bars)

		# 2: Place the necessary orders for positions marked to exit on session close.
		self.__checkExitOnSessionClose(bars)

		# 3: Notify that the bars were processed.
		self.__barsProcessedEvent.emit(self, bars)

	def run(self):
		"""Call once (**and only once**) to backtest the strategy. """
		try:
			self.__feed.getNewBarsEvent().subscribe(self.__onBars)
			self.__feed.start()
			self.__broker.start()
			self.onStart()

			# Dispatch events as long as the feed or the broker have something to dispatch.
			stopDispBroker = self.__broker.stopDispatching()
			stopDispFeed = self.__feed.stopDispatching()
			while not stopDispFeed or not stopDispBroker:
				if not stopDispBroker:
					self.__broker.dispatch()
				if not stopDispFeed:
					self.__feed.dispatch()
				stopDispBroker = self.__broker.stopDispatching()
				stopDispFeed = self.__feed.stopDispatching()

			if self.__feed.getLastBars() != None:
				self.onFinish(self.__feed.getLastBars())
			else:
				raise Exception("Feed was empty")
		finally:
			self.__feed.getNewBarsEvent().unsubscribe(self.__onBars)
			self.__broker.stop()
			self.__feed.stop()
			self.__broker.join()
			self.__feed.join()
