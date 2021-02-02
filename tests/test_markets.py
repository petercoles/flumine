import unittest
import datetime
from unittest import mock

from flumine.markets.markets import Markets
from flumine.markets.market import Market, OrderPackageType, ControlError


class MarketsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.markets = Markets()

    def test_init(self):
        self.assertEqual(self.markets._markets, {})

    def test_add_market(self):
        mock_market = mock.Mock()
        self.markets.add_market("1.1", mock_market)
        self.assertEqual(self.markets._markets, {"1.1": mock_market})

    def test_add_market_reopen(self):
        mock_market = mock.Mock()
        self.markets._markets = {"1.1": mock_market}
        self.markets.add_market("1.1", mock_market)

        self.assertEqual(self.markets._markets, {"1.1": mock_market})
        mock_market.open_market.assert_called_with()

    def test_close_market(self):
        mock_market = mock.Mock()
        self.markets._markets = {"1.1": mock_market}
        self.markets.close_market("1.1")
        mock_market.close_market.assert_called_with()

    def test_remove_market(self):
        mock_market = mock.Mock()
        self.markets._markets = {"1.1": mock_market}
        self.markets.remove_market("1.1")
        self.assertEqual(self.markets._markets, {})

    def test_get_order(self):
        mock_market = mock.Mock()
        mock_market.closed = False
        mock_market.blotter = {"test": 12}
        self.markets._markets = {"1.1": mock_market}

        self.assertEqual(self.markets.get_order("1.1", "test"), 12)
        self.assertIsNone(self.markets.get_order("1.2", "test"))

    def test_get_order_from_bet_id(self):
        mock_order = mock.Mock()
        mock_order.bet_id = "321"
        mock_market = mock.Mock()
        mock_market.closed = False
        mock_market.blotter.__iter__ = mock.Mock(return_value=iter([mock_order]))
        self.markets._markets = {"1.1": mock_market}

        self.assertEqual(self.markets.get_order_from_bet_id("1.1", "321"), mock_order)
        self.assertIsNone(self.markets.get_order("1.2", "test"))

    def test_markets(self):
        self.assertEqual(self.markets.markets, {})
        mock_market = mock.Mock()
        mock_market_two = mock.Mock()
        self.markets._markets = {"1.1": mock_market, "2.1": mock_market_two}
        self.assertEqual(
            self.markets.markets, {"1.1": mock_market, "2.1": mock_market_two}
        )

    def test_open_market_ids(self):
        self.assertEqual(self.markets.open_market_ids, [])
        mock_market = mock.Mock()
        mock_market.closed = False
        mock_market_two = mock.Mock()
        mock_market_two.closed = True
        self.markets._markets = {"1.1": mock_market, "2.1": mock_market_two}
        self.assertEqual(self.markets.open_market_ids, [mock_market.market_id])

    def test_live_orders(self):
        self.assertFalse(self.markets.live_orders)
        mock_market = mock.Mock()
        mock_market.closed = False
        mock_market.blotter.has_live_orders = True
        self.markets._markets = {"1.234": mock_market}
        self.assertTrue(self.markets.live_orders)
        mock_market.blotter.has_live_orders = False
        self.assertFalse(self.markets.live_orders)

    def test_iter(self):
        self.assertEqual(len([i for i in self.markets]), 0)

    def test_len(self):
        self.assertEqual(len(self.markets), 0)


class MarketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_flumine = mock.Mock()
        self.mock_market_book = mock.Mock()
        self.mock_market_catalogue = mock.Mock()
        self.market = Market(
            self.mock_flumine,
            "1.234",
            self.mock_market_book,
            self.mock_market_catalogue,
        )

    def test_init(self):
        self.assertEqual(self.market.flumine, self.mock_flumine)
        self.assertEqual(self.market.market_id, "1.234")
        self.assertFalse(self.market.closed)
        self.assertIsNone(self.market.date_time_closed)
        self.assertEqual(self.market.market_book, self.mock_market_book)
        self.assertEqual(self.market.market_catalogue, self.mock_market_catalogue)
        self.assertTrue(self.market.update_market_catalogue)
        self.assertEqual(self.market.context, {"simulated": {}})

    def test_call(self):
        mock_market_book = mock.Mock()
        self.market(mock_market_book)
        self.assertEqual(self.market.market_book, mock_market_book)
        self.assertTrue(self.market.update_market_catalogue)

    def test_open_market(self):
        self.market.open_market()
        self.assertFalse(self.market.closed)

    def test_close_market(self):
        self.market.close_market()
        self.assertTrue(self.market.closed)
        self.assertIsNotNone(self.market.date_time_closed)

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=True)
    @mock.patch("flumine.markets.market.Market._create_order_package")
    @mock.patch("flumine.markets.market.events")
    def test_place_order(
        self, mock_events, mock__create_order_package, mock__validate_controls
    ):
        mock_order = mock.Mock(id="123")
        mock_order.trade.market_notes = None
        self.assertTrue(self.market.place_order(mock_order))
        mock_order.place.assert_called_with(self.market.market_book.publish_time)
        self.mock_flumine.log_control.assert_called_with(mock_events.TradeEvent())
        mock_order.trade.update_market_notes.assert_called_with(self.market)
        mock__create_order_package.assert_called_with(
            [mock_order], OrderPackageType.PLACE, None
        )
        self.mock_flumine.process_order_package.assert_called_with(
            mock__create_order_package()
        )
        mock__validate_controls.assert_called_with(mock_order, OrderPackageType.PLACE)

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=True)
    @mock.patch("flumine.markets.market.Market._create_order_package")
    @mock.patch("flumine.markets.market.events")
    def test_place_order_not_executed(
        self, mock_events, mock__create_order_package, mock__validate_controls
    ):
        mock_order = mock.Mock(id="123")
        self.assertTrue(self.market.place_order(mock_order, execute=False))
        mock_order.place.assert_called_with(self.market.market_book.publish_time)
        self.mock_flumine.log_control.assert_called_with(mock_events.TradeEvent())
        mock__create_order_package.assert_not_called()

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=True)
    @mock.patch("flumine.markets.market.Market._create_order_package")
    def test_place_order_retry(
        self, mock__create_order_package, mock__validate_controls
    ):
        mock_order = mock.Mock()
        self.market.blotter._orders = {mock_order.id: mock_order}
        self.assertTrue(self.market.place_order(mock_order))
        mock__create_order_package.assert_not_called()

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=False)
    def test_place_order_violation(self, mock__validate_controls):
        mock_order = mock.Mock()
        self.assertFalse(self.market.place_order(mock_order))
        mock__validate_controls.assert_called_with(mock_order, OrderPackageType.PLACE)

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=True)
    @mock.patch("flumine.markets.market.Market._create_order_package")
    def test_cancel_order(self, mock__create_order_package, mock__validate_controls):
        mock_order = mock.Mock()
        self.assertTrue(self.market.cancel_order(mock_order, 0.01))
        mock_order.cancel.assert_called_with(0.01)
        mock__create_order_package.assert_called_with(
            [mock_order], OrderPackageType.CANCEL
        )
        self.mock_flumine.process_order_package.assert_called_with(
            mock__create_order_package()
        )
        mock__validate_controls.assert_called_with(mock_order, OrderPackageType.CANCEL)

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=False)
    def test_cancel_order_violation(self, mock__validate_controls):
        mock_order = mock.Mock()
        self.assertFalse(self.market.cancel_order(mock_order))
        mock__validate_controls.assert_called_with(mock_order, OrderPackageType.CANCEL)

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=True)
    @mock.patch("flumine.markets.market.Market._create_order_package")
    def test_update_order(self, mock__create_order_package, mock__validate_controls):
        mock_order = mock.Mock()
        self.assertTrue(self.market.update_order(mock_order, "PERSIST"))
        mock_order.update.assert_called_with("PERSIST")
        mock__create_order_package.assert_called_with(
            [mock_order], OrderPackageType.UPDATE
        )
        self.mock_flumine.process_order_package.assert_called_with(
            mock__create_order_package()
        )
        mock__validate_controls.assert_called_with(mock_order, OrderPackageType.UPDATE)

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=False)
    def test_update_order_violation(self, mock__validate_controls):
        mock_order = mock.Mock()
        self.assertFalse(self.market.update_order(mock_order, "test"))
        mock__validate_controls.assert_called_with(mock_order, OrderPackageType.UPDATE)

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=True)
    @mock.patch("flumine.markets.market.Market._create_order_package")
    def test_replace_order(self, mock__create_order_package, mock__validate_controls):
        mock_order = mock.Mock()
        self.assertTrue(self.market.replace_order(mock_order, 1.01, 321))
        mock_order.replace.assert_called_with(1.01)
        mock__create_order_package.assert_called_with(
            [mock_order], OrderPackageType.REPLACE, 321
        )
        self.mock_flumine.process_order_package.assert_called_with(
            mock__create_order_package()
        )
        mock__validate_controls.assert_called_with(mock_order, OrderPackageType.REPLACE)

    @mock.patch("flumine.markets.market.Market._validate_controls", return_value=False)
    def test_replace_order_violation(self, mock__validate_controls):
        mock_order = mock.Mock()
        self.assertFalse(self.market.replace_order(mock_order, 2.02))
        mock__validate_controls.assert_called_with(mock_order, OrderPackageType.REPLACE)

    def test__validate_controls(self):
        mock_trading_control = mock.Mock()
        mock_client_control = mock.Mock()
        self.market.flumine.trading_controls = [mock_trading_control]
        self.market.flumine.client.trading_controls = [mock_client_control]
        mock_order = mock.Mock()
        mock_package_type = mock.Mock()
        self.assertTrue(self.market._validate_controls(mock_order, mock_package_type))
        mock_trading_control.assert_called_with(mock_order, mock_package_type)
        mock_client_control.assert_called_with(mock_order, mock_package_type)

    def test__validate_controls_violation(self):
        mock_trading_control = mock.Mock()
        mock_trading_control.side_effect = ControlError("test")
        mock_client_control = mock.Mock()
        self.market.flumine.trading_controls = [mock_trading_control]
        self.market.flumine.client.trading_controls = [mock_client_control]
        mock_order = mock.Mock()
        mock_package_type = mock.Mock()
        self.assertFalse(self.market._validate_controls(mock_order, mock_package_type))
        mock_trading_control.assert_called_with(mock_order, mock_package_type)
        mock_client_control.assert_not_called()

    @mock.patch("flumine.markets.market.BetfairOrderPackage")
    def test__create_order_package(self, mock_betfair_order_package):
        package = self.market._create_order_package([1, 2], OrderPackageType.PLACE, 123)
        mock_betfair_order_package.assert_called_with(
            client=self.market.flumine.client,
            market_id=self.market.market_id,
            orders=[1, 2],
            package_type=OrderPackageType.PLACE,
            bet_delay=self.market.market_book.bet_delay,
            market_version=123,
        )
        self.assertEqual(package, mock_betfair_order_package())

    def test_event(self):
        mock_market_catalogue = mock.Mock()
        mock_market_catalogue.event.id = 12
        self.market.market_catalogue = mock_market_catalogue

        self.market.flumine.markets = []
        self.assertEqual(self.market.event, {})

        m_one = mock.Mock(market_type=1, event_id=12)
        m_two = mock.Mock(market_type=2, event_id=12)
        m_three = mock.Mock(market_type=3, event_id=123)
        m_four = mock.Mock(market_type=1, event_id=12)
        self.market.flumine.markets = [m_one, m_two, m_three, m_four]
        self.assertEqual(self.market.event, {1: [m_one, m_four], 2: [m_two]})

    def test_event_type_id_mc(self):
        mock_market_catalogue = mock.Mock()
        self.market.market_catalogue = mock_market_catalogue
        self.assertEqual(self.market.event_type_id, mock_market_catalogue.event_type.id)

    def test_event_type_id_mb(self):
        self.market.market_catalogue = None
        mock_market_book = mock.Mock()
        self.market.market_book = mock_market_book
        self.assertEqual(
            self.market.event_type_id, mock_market_book.market_definition.event_type_id
        )

    def test_event_id_mc(self):
        mock_market_catalogue = mock.Mock()
        self.market.market_catalogue = mock_market_catalogue
        self.assertEqual(self.market.event_id, mock_market_catalogue.event.id)

    def test_event_id_mb(self):
        self.market.market_catalogue = None
        mock_market_book = mock.Mock()
        self.market.market_book = mock_market_book
        self.assertEqual(
            self.market.event_id, mock_market_book.market_definition.event_id
        )

    def test_market_type_mc(self):
        mock_market_catalogue = mock.Mock()
        self.market.market_catalogue = mock_market_catalogue
        self.assertEqual(
            self.market.market_type, mock_market_catalogue.description.market_type
        )

    def test_market_type_mb(self):
        self.market.market_catalogue = None
        mock_market_book = mock.Mock()
        self.market.market_book = mock_market_book
        self.assertEqual(
            self.market.market_type, mock_market_book.market_definition.market_type
        )

    def test_seconds_to_start(self):
        mock_market_catalogue = mock.Mock()
        mock_market_catalogue.market_start_time = datetime.datetime.utcfromtimestamp(1)
        self.market.market_catalogue = mock_market_catalogue
        self.assertLess(self.market.seconds_to_start, 0)

    def test_seconds_to_start_market_book(self):
        self.market.market_catalogue = None
        mock_market_book = mock.Mock()
        mock_market_book.market_definition.market_time = (
            datetime.datetime.utcfromtimestamp(1)
        )
        self.market.market_book = mock_market_book
        self.assertLess(self.market.seconds_to_start, 0)

    def test_seconds_to_start_market_catalogue(self):
        self.market.market_catalogue.market_start_time = (
            datetime.datetime.utcfromtimestamp(1)
        )
        self.assertLess(self.market.seconds_to_start, 0)

    def test_seconds_to_start_none(self):
        self.market.market_book = None
        self.market.market_catalogue = None
        self.assertLess(self.market.seconds_to_start, 0)

    def test_elapsed_seconds_closed(self):
        self.assertIsNone(self.market.elapsed_seconds_closed)
        self.market.closed = True
        self.market.date_time_closed = datetime.datetime.utcnow()
        self.assertGreaterEqual(self.market.elapsed_seconds_closed, 0)

    def test_event_name_mc(self):
        mock_market_catalogue = mock.Mock()
        self.market.market_catalogue = mock_market_catalogue
        self.assertEqual(self.market.event_name, mock_market_catalogue.event.name)

    def test_event_name_mb(self):
        self.market.market_catalogue = None
        mock_market_book = mock.Mock()
        self.market.market_book = mock_market_book
        self.assertEqual(
            self.market.event_name, mock_market_book.market_definition.event_name
        )

    def test_country_code_mc(self):
        mock_market_catalogue = mock.Mock()
        self.market.market_catalogue = mock_market_catalogue
        self.assertEqual(
            self.market.country_code, mock_market_catalogue.event.country_code
        )

    def test_country_code_mb(self):
        self.market.market_catalogue = None
        mock_market_book = mock.Mock()
        self.market.market_book = mock_market_book
        self.assertEqual(
            self.market.country_code, mock_market_book.market_definition.country_code
        )

    def test_venue_mc(self):
        mock_market_catalogue = mock.Mock()
        self.market.market_catalogue = mock_market_catalogue
        self.assertEqual(self.market.venue, mock_market_catalogue.event.venue)

    def test_venue_mb(self):
        self.market.market_catalogue = None
        mock_market_book = mock.Mock()
        self.market.market_book = mock_market_book
        self.assertEqual(self.market.venue, mock_market_book.market_definition.venue)

    def test_race_type_mc(self):
        mock_market_catalogue = mock.Mock()
        self.market.market_catalogue = mock_market_catalogue
        self.assertEqual(
            self.market.race_type, mock_market_catalogue.description.race_type
        )

    def test_race_type_mb(self):
        self.market.market_catalogue = None
        mock_market_book = mock.Mock()
        self.market.market_book = mock_market_book
        self.assertEqual(
            self.market.race_type, mock_market_book.market_definition.race_type
        )

    def test_info(self):
        self.assertEqual(
            self.market.info,
            {
                "market_id": self.market.market_id,
                "event_id": self.market.event_id,
                "event_type_id": self.market.event_type_id,
                "event_name": self.market.event_name,
                "market_type": self.market.market_type,
                "market_start_datetime": str(self.market.market_start_datetime),
                "country_code": self.market.country_code,
                "venue": self.market.venue,
                "race_type": self.market.race_type,
            },
        )
