# ИМПОРТИРОВАНИЕ БИБЛИОТЕК
from binance_api import Binance  # ОСНОВНАЯ БИБЛИОТЕКА BINANCE

import requests
import json
import pandas as pd
import numpy as np
import time
import datetime
import matplotlib
#from binance.client import Clientpip
import traceback

# ----------------------------------------------------------------------НАСТРОЙКИ
# КЛЮЧИ API И SECRET

API_KEY = ""
API_SECRET = ""

bot = Binance(API_KEY=API_KEY, API_SECRET=API_SECRET)

# ПАРА ДЛЯ РАБОТЫ
baseCoin = 'BTC'  # основная валюта
secCoin = 'USDT'  # вторичная валюта
pair = baseCoin + secCoin  # итоговая пара

secVol = 15  # количество вторичной валюты для торговли

# ПЕРИОД ДЛЯ РАБОТЫ
period = '1m'

# ПАУЗА МЕЖДУ ЗАПРОСАМИ
reqSleep = 1

# ПАУЗА МЕЖДУ ЦИКЛАМИ ПРОГРАММЫ
cycleSleep = 10

# РЕКОМЕНДУЕМЫЙ ОБЪЕМ ПРОФИТА - деньги полученные в результате торговлю. Разница между потраченным объемом и полученной выручкой
take_profit = 0.04  # 1 процент

# ПОРОГОВЫЕ ЗНАЧЕНИЯ ДЛЯ RSI
RSImin = 35  # МИНИМУМ
RSImax = 70  # МАКСИМУМ
RSI_SIGNAL = 3  # СКОЛЬКО ЗНАЧЕНИЙ БЕРЕМ ДЛЯ ПОИСКА СИГНАЛА

# ПЕРИОДЫ ДЛЯ SMA - скользящая средняя
fastPeriod = 9
slowPeriod = 16


# ----------------------------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------ФУНКЦИИ-------------------------------------------------------------------
# ----------------------ПРОВЕРКА БАЛАНСА
def get_balance(bc, sc):
	coinList = []  # свойства монеты
	balList = []  # лист с балансами
	bal = bot.account(recvWindow=60000)['balances']
	for b in bal:
		if b['asset'] == bc or b['asset'] == sc:
			coinList.append(b['asset'])
			coinList.append(b['free'])
			balList.append(coinList)
			coinList = []
	return balList


# ----------------------ПРОВЕРКА ОРДЕРОВ
def get_orders():
	orders = bot.openOrders(recvWindow=60000)
	ticker = bot.tickerPrice(symbol=pair)

	# если ордеров нет - продолжаем работу
	if len(orders) == 0:
		return 0
	else:
		for ord in orders:
			oSide = ord['side']
			oSymbol = ord['symbol']
			oId = ord['orderId']
			oPrice = ord['price']
			oVolume = ord['origQty']
			oExecuted = ord['executedQty']
			print('>> ОТКРЫТ ОРДЕР: ', oSide, 'ПАРА:', oSymbol, 'ОБЪЕМ:', oVolume, 'ЦЕНА:', oPrice, 'ИСПОЛНЕНО:', oExecuted, 'АКТУАЛЬНАЯ ЦЕНА:', ticker['price'])
		return 1


# ----------------------ПОЛУЧЕНИЕ ПОЗИЦИИ ДЛЯ ПОКУПКИ
def get_buy_position():
	# ПОЛУЧАЕМ ДАТАФРЕЙМ ПО НУЖНОЙ ПАРЕ
	ndf = get_dataframes(pair)

	# ПОДКЛЮЧАЕМ СТРАТЕГИЮ
	ndf = sma_strategy(ndf)

	# ТАК КАК СИГНАЛ ФОРМИРУЕТСЯ ОТ ПОСЛЕДНИХ ДАННЫХ ТО ПРОВЕРЯЕМ ПРЕДПОСЛЕДНИЕ
	signalList = ndf.tail(2)['SIGNAL'].tolist()[0]
	price = float(ndf.tail(2)['Close'].tolist()[0])
	print("get_buy_position() ПОСЛЕДНИЙ СИГНАЛ: ", signalList)

	# ПРОВЕРКА НАЛИЧИЯ СИГНАЛА И ВЫВОД ИЗ ФУНКЦИИ
	if signalList == 'BUY':
		return price
	else:
		return 0


# ----------------------ПОЛУЧЕНИЕ ДАТАФРЕЙМА ДЛЯ АНАЛИЗА
def get_dataframes(listen_pair):
	# НАЗВАНИЯ КОЛОНОК
	cols = ["Time", "Open", "High", "Low", "Close", "Volume", "CloseTime", "QuoteAsseVolume", "NumberOfTrades", "TakerBaseVolume", "TakerQuoteVolume", "Ignore"]

	# ЗАПРОС ИСТОРИИ ТОРГОВЫХ СВЕЧЕЙ
	klines = bot.klines(symbol=listen_pair, interval=period, limit=1000)
	df = pd.DataFrame(klines, columns=cols)

	# ЧИСТКА И ПОДГОТОВКА ДАННЫХ
	del df['High']
	del df['Low']
	del df['Open']
	del df['Volume']
	del df['CloseTime']
	del df['QuoteAsseVolume']
	del df['TakerBaseVolume']
	del df['TakerQuoteVolume']
	del df['Ignore']
	del df['NumberOfTrades']

	df["Time"] = pd.to_datetime(df["Time"], yearfirst=True, unit="ms")
	df["Close"] = pd.to_numeric(df["Close"])

	# ПРЕДВАРИТЕЛЬНЫЕ ВЫЧИСЛЕНИЯ
	df['Change'] = df['Close'].diff()

	# ДОБАВЛЯЕМ RSI
	df = calcRSI(df)

	# ДОБАВЛЯЕМ MACD
	df = calcMACD(df)

	# #ДОБАВЛЯЕМ SMA-CROSS
	# ВЫЧИСЛЯЕМ SMA
	df = calcSMA(df)

	# ДОБАВЛЯЕМ
	return df


# ----------------------ПОЛУЧЕНИЕ ПОЗИЦИИ ДЛЯ ПРОДАЖИ
def get_sell_position(lCost):
	lCost = round(float(lCost))
	print('ПОДБИРАЕМ ПОЗИЦИЮ ДЛЯ ПРОДАЖИ', lCost)

	# --------------------------------------------------СТРАТЕГИЯ ПРОДАЖИ "МИНИМАЛЬНЫЙ ПРОФИТ"
	# ЗАПРОС ОБЪЕМА ПОСЛЕДНЕЙ ПОКУПКИ
	# ЗАПРОС ОБЪЕМА СРЕДСТВ НА БАЛАНСЕ
	# ВЫЧИСЛЕНИЕ НЕОБХОДИМОЙ ЦЕНЫ ДЛЯ ПОЛУЧЕНИЯ
	# ЗНАЯ ТОРГУЕМЫЙ ОБЪЕМ
	# Пример - купили по 35, продали по 35,20 - вышли в 0

	print('СТРАТЕГИЯ "ПРОФИТ ПО ЦЕНЕ":')

	myTrades = bot.myTrades(recvWindow=6000, symbol=pair)
	mtrades = pd.DataFrame(myTrades).tail(1)

	lastSecVol = float(mtrades['quoteQty'])
	lastPriVol = float(mtrades['qty'])
	lastprice = float(mtrades['price'])
	print('------------------------------')
	print('В ПОСЛЕДНЕЙ СДЕЛКЕ БЫЛО КУПЛЕНО:')
	print(lastPriVol)
	print('ПО: ', lastprice)
	print('ПОТРАТИЛИ :', lastSecVol)
	print('УСТАНОВЛЕННЫЙ ПОРОГ ПРОФИТА:', take_profit)
	print('------------------------------')

	# ВЫЧИСЛЯЕМ ПРОФИТ
	sell_Price = round(lastprice + 100, 2)
	sell_Vol = lastPriVol - lastPriVol * 0.001
	print('ПЛАНИРУЕМАЯ ЦЕНА ПРОДАЖИ:', sell_Price)
	print('ПЛАНИРУЕМЫЙ ОБЪЕМ ПРОДАЖИ:', sell_Vol)

	return sell_Price, sell_Vol


# ----------------------ПОСТАНОВКА ОРДЕРА ДЛЯ ПОКУПКИ
def make_buy_order(buyPrice):
	print('ОТКРЫТ ОРДЕР НА ПОКУПКУ')
	print('--------------')
	trVol = round(secVol / buyPrice, 5)
	buyOrd = bot.createOrder(symbol=pair, recvWindow=60000, side='BUY', type='LIMIT', timeInForce='GTC', quantity=trVol, price=buyPrice)
	print('ПАРА:\t', pair)
	print('ЦЕНА:\t', buyPrice)
	print('КОЛИЧЕСТВО:\\t', trVol)
	print('СТОРОНА:\tBUY')
	print('ТИП:\tLIMIT')
	print('--------------')


# ----------------------ПОСТАНОВКА ОРДЕРА ДЛЯ ПРОДАЖИ
def make_sell_order(sellPrice, sellVol):
	print('ОТКРЫТ ОРДЕР НА ПРОДАЖУ')
	buyOrd = bot.createOrder(symbol=pair, recvWindow=60000, side='SELL', type='LIMIT', timeInForce='GTC', quantity=sellVol, price=sellPrice)

	print('--------------')
	print('ПАРА:\t', pair)
	print('ЦЕНА:\t', sellPrice)
	print('КОЛИЧЕСТВО:\t', sellVol)
	print('СТОРОНА:\tSELL')
	print('ТИП:\tLIMIT')
	print('--------------')


# ---------------------------------------------------------СТРАТЕГИИ-----------------------------------------------------------------
# ----------------------СТРАТЕГИЯ ПЕРЕСЕЧЕНИЕ RSI И MACD < 0
def rsi_strategy(bdf):
	rsiSeries = bdf['RSI']
	rsi = rsiSeries.tolist()

	ACTION = []

	# ПРОВЕРКА ПЕРЕСЕЧЕНИЯ RSI C ГРАНИЦАМИ
	for i in range(1, len(rsi)):
		# СНИЗУ
		if rsi[i] > RSImin and rsi[i - 1] < RSImin:
			ACTION.append('BUY')
		# СВЕРХУ
		elif rsi[i] < RSImax and rsi[i - 1] > RSImax:
			ACTION.append('SELL')
		else:
			ACTION.append('HOLD')

	ACTION.append('HOLD')
	bdf['RSIAction'] = ACTION

	# print(bdf)
	return (bdf)


# ----------------------СТРАТЕГИЯ ПЕРЕСЕЧЕНИЕ SMA
def sma_strategy(bdf):
	sma_action = []
	smaFast = bdf['smaFast'].tolist()
	smaSlow = bdf['smaSlow'].tolist()

	for s in range(1, len(smaFast)):
		if smaFast[s] < smaSlow[s] and smaFast[s - 1] > smaSlow[s - 1]:
			sma_action.append('BUY')
		elif smaFast[s] > smaSlow[s] and smaFast[s - 1] < smaSlow[s - 1]:
			sma_action.append('SELL')
		else:
			sma_action.append('HOLD')
	sma_action.append('HOLD')
	bdf['SIGNAL'] = sma_action
	return (bdf)


# ----------------------------------------------------------------------------------------------------------------------------------
# ---------------------------------------------------ИНДИКАТОРЫ---------------------------------------------------------------------
# ----------------------------------RSI
def calcRSI(ndf):
	# ВЫЧИСЛЯЕМ RSI
	# ВЫЧИСЛЯЕМ ПОЛОЖИТЕЛЬНЫЕ И ОТРИЦАТЕЛЬНЫЕ ТЕНДЕНЦИИ
	ndf['GAIN'] = np.select([ndf['Change'] > 0, ndf['Change'].isna()], [ndf['Change'], np.nan], default=0)
	ndf['LOSS'] = np.select([ndf['Change'] < 0, ndf['Change'].isna()], [-ndf['Change'], np.nan], default=0)
	# ЗАКРЫВАЕМ ПРОПУСКИ В ДАННЫХ
	ndf['GAIN'].fillna(0, inplace=True)
	ndf['LOSS'].fillna(0, inplace=True)
	# ВЫЧИСЛЯЕМ СРЕДНЕЕ У РОСТА И ПАДЕНИЯ
	ndf['AVG_GAIN'] = ndf['GAIN'].rolling(window=14).mean()
	ndf['AVG_LOSS'] = ndf['LOSS'].rolling(window=14).mean()
	# ВЫЧИСЛЯЕМ RS
	ndf['RS'] = round(ndf['AVG_GAIN'] / ndf['AVG_LOSS'], 8)
	# ВЫЧИСЛЯЕМ RSI
	ndf['RSI'] = round(100 - 100 / (1 + ndf['RS']), 2)
	ndf['RSI_MIN'] = RSImin
	ndf['RSI_MAX'] = RSImax
	del ndf['RS']
	del ndf['AVG_GAIN']
	del ndf['AVG_LOSS']
	del ndf['GAIN']
	del ndf['LOSS']
	return (ndf)


# ----------------------------------MACD
def calcMACD(ndf):
	# ВЫЧИСЛЯЕМ MACD
	ndf['exp1'] = ndf['Close'].ewm(span=12, adjust=False).mean()
	ndf['exp2'] = ndf['Close'].ewm(span=26, adjust=False).mean()
	ndf['MACD'] = ndf['exp1'] - ndf['exp2']
	ndf['exp3'] = ndf['MACD'].ewm(span=9, adjust=False).mean()

	del ndf['exp1']
	del ndf['exp2']

	# print(ndf)
	return ndf


# ----------------------------------SMA
def calcSMA(ndf):
	ndf['smaFast'] = ndf['Close'].rolling(window=fastPeriod).mean()
	ndf['smaSlow'] = ndf['Close'].rolling(window=slowPeriod).mean()
	return ndf


lastCost = None
balance = None


# ---------------------------------------------------ОСНОВНОЙ ХОД ПРОГРАММЫ---------------------------------------------------------
def make_trade(pos):
	global lastCost, balance

	# ЕСЛИ ПОЗИЦИЯ ОПРЕДЕЛЕНА КАК ПОКУПКА - ПОКУПАЕМ
	if pos == 'BUY':
		# ЖДЕМ МОМЕНТ ДЛЯ ПОКУПКИ
		print('----ПОИСК ПОЗИЦИИ НА ПОКУПКУ---')
		print('-------------------------------')
		buyprice = 0

		# ЦИКЛ ПОИСКА ПОЗИЦИИ НА ПОКУПКУ
		while buyprice == 0:
			# ВЫЗОВ ФУНКЦИИ ПОИСКА ПОЗИЦИИ ДЛЯ ПОКУПКИ
			buyprice = get_buy_position()
			print('>> ПОЗИЦИЯ НЕ ПОДХОДИТ ДЛЯ ПОКУПКИ. ОЖИДАНИЕ 10 С')
			timer = '.'
			for s in range(1, 10):
				timer = timer + "."
				print(timer)
				time.sleep(1)

		print('-------------------------------')
		print('>> НАЙДЕНА ПОЗИЦИЯ ДЛЯ ПОКУПКИ')
		print('---------------')

		# ВЫСТАВЛЯЕМ ОРДЕР ПО НАСТРОЙКАМ
		orddr = make_buy_order(buyprice)
		# buyedVolume = orddr['origQty']

		# ЖДЕМ ЗАКРЫТИЯ ОРДЕРОВ
		orders = get_orders()
		while orders != 0:
			orders = get_orders()
			time.sleep(5)
		print('>> ОРДЕР НА ПОКУПКУ ЗАКРЫТ')

		# ПЕРЕВОДИМ В РЕЖИМ ПРОДАЖИ
		pos = 'SELL'
		print('УСТАНОВЛЕН РЕЖИМ SELL')
		return pos

	# ЕСЛИ ПОЗИЦИЯ ОПРЕДЕЛЕНА КАК ЗАКУПЛЕННАЯ - ПРОДАЕМ
	elif pos == 'SELL':
		# ЖДЕМ МОМЕНТ ДЛЯ ПРОДАЖИ
		sellPrice, sellVol = get_sell_position(lastCost)
		# ПРОДАЕМ ВСЕ ЧТО ЕСТЬ
		# ВЫСТАВЛЯЕМ ОРДЕР НА ПРОДАЖУ
		make_sell_order(sellPrice, round(sellVol, 6))
		time.sleep(3)
		# ЖДЕМ ЗАКРЫТИЯ ОРДЕРА
		orders = get_orders()

		while orders != 0:
			orders = get_orders()
			time.sleep(5)

		print('>> ОРДЕР НА ПРОДАЖУ ЗАКРЫТ')

		# ПЕРЕВОДИМ В РЕЖИМ ПОДВЕДЕНИЯ ИТОГОВ
		pos = 'END'
		print('GET END POSITION')
		return pos

	elif pos == 'END':
		# ЗАПРАШИВАЕМ ИТОГОВЫЙ БАЛ45АНС
		print('БАЛАНС В НАЧАЛЕ СДЕЛКИ')
		oldBalance = float(balance[1][1])
		print(oldBalance)

		nBal = get_balance(baseCoin, secCoin)
		print('------------------------------')
		print('БАЛАНС В КОНЦЕ СДЕЛКИ:')
		newBalance = float(nBal[1][1])
		print(newBalance)
		print('------------------------------')
		print('ПРОФИТ:')
		print(newBalance - oldBalance)
		print('------------------------------')

		# ВЫВОДИМ РЕЗУЛЬТАТ
		# ВЫХОДИМ ИЗ ГЛАВНОГО ЦИКЛА
		print('END oF PROGRAM')
		pos = 'START'
		return pos
	else:
		print('make_trade: Позиция ' + pos + " не распознана")


def main_loop():
	global lastCost, balance

	mode = 1  # режим, при котором программа выполняется в цике (0 - для выполнения только оболочки)
	position = 'START'  # позиция входа
	orders = 1  # переменная для начального хранения статуса ордеров

	# ------------------------------------------------ОБОЛОЧКА ПРОГРАММЫ ДЛЯ ЗАЦИКЛИВАНИЯ
	# НАЧАЛО РАБОТЫ
	print('------------------------------')
	print('----                     -----')
	print('----     TRADER V 0.1    -----')
	print('----                     -----')
	print('------------------------------')
	print('         НАЧАЛО РАБОТЫ        ')
	print('------------------------------')

	print('------------------------------')
	print(' ПРОВЕРКА УСЛОВИЙ ДЛЯ ТОРГОВЛИ')
	print('------------------------------')
	# ВЫВОДИМ ИНФОРМАЦИЮ ОБ АККАУНТЕ
	balance = get_balance(baseCoin, secCoin)
	print('')
	print('----     ТЕКУЩИЙ БАЛАНС  -----')
	print('БАЗОВАЯ ВАЛЮТА:\t', balance[0][0], balance[0][1])
	print('ВТОРОСТЕПЕННАЯ ВАЛЮТА:\t', balance[1][0], balance[1][1])
	print('------------------------------')

	# ОПРЕДЕЛЛЯЕМ ПОЗИЦИЮ НА РЫНКЕ ПО ПОСЛЕДНЕМУ ОРДЕРУ
	myTrades = bot.myTrades(recvWindow=6000, symbol=pair)
	if myTrades:
		trdf = pd.DataFrame(myTrades)
		trdf['time'] = pd.to_datetime(trdf['time'], yearfirst=True, unit="ms")

		isBuyer = trdf['isBuyer'].tolist()

		lastCosts = trdf['price'].tolist()
		lastCost = round(float(lastCosts[-1]), 2)

		if isBuyer[-1] == True:
			position = 'SELL'
			print('ТЕКУЩАЯ ПОЗИЦИЯ: ', position)
			print('ПОСЛЕДНИМ ДЕЙСТВИЕМ БЫЛА ПОКУПКА ПО ЦЕНЕ: ', lastCost)

		elif not isBuyer[-1]:
			position = 'BUY'
			print('ТЕКУЩАЯ ПОЗИЦИЯ: ', position)
			print('ПОСЛЕДНИМ ДЕЙСТВИЕМ БЫЛА ПРОДАЖА ПО ЦЕНЕ: ', lastCost)
	else:
		print('--СДЕЛАЙТЕ ХОТЯБЫ 1 ОРДЕР' + pair + '--')
		print('-------------------------------')
		exit(0)

	print('------------------------------')

	# ПРОВЕРЯЕМ НАЛИЧИЕ ОТКРЫТЫХ ОРДЕРОВ
	print('')
	print('------------------------------')
	print('---- ПОИСК ОТКРЫТЫХ ОРДЕРОВ --')
	print('------------------------------')

	orders = get_orders()

	# ЕСЛИ ЕСТЬ ОТКРЫТЫЕ ОРДЕРА - ЖДЕМ ЗАКРЫТИЯ
	while orders != 0:

		timer = ""
		orders = get_orders()

		for s in range(1, 10):
			timer = timer + "."
			print(timer)
			time.sleep(1)

	print('--ОТКРЫТЫЕ ОРДЕРА ОТСУТСТВУЮТ--')
	print('-------------------------------')

	# ЗДЕСЬ БУДЕТ УСЛОВИЕ ПРОВЕРКИ ДОСТАТОЧНОСТИ БАЛАНСА
	if secVol > float(balance[1][1]) and float(balance[0][1]) < 0.0001:
		print('------------------------------')
		print('----НЕДОСТАТОЧНО СРЕДСТВ -----')
		print('------ДЛЯ ВХОДА В СДЕЛКУ------')
		print('-ПРОВЕРЬТЕ БАЛАНС И НАСТРОЙКИ-')
		exit()

	print('------------------------------')
	print('----- СРЕДСТВ ДОСТАТОЧНО -----')
	print('------------------------------')

	# ПЕРЕХОД В ОСНОВНОЙ ЦИКЛ ПРОГРАММЫ
	while mode != 0:
		try:
			position = make_trade(position)
			if position == 'START':
				break
		except:
			traceback.print_exc()
			print('Необрабатываемая ошибка, продолжение работы')
		time.sleep(cycleSleep)
		mode = 1

	print('ОТРАБОТАЛИ')


def main():
	while 1:
		try:
			main_loop()
		except:
			traceback.print_exc()
			print('ошибка в main_loop')


if __name__ == '__main__':
	main()

