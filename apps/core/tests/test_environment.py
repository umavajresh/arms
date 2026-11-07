from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.environment import (
    read_bool,
    read_int,
    read_list,
    read_required,
    read_required_list,
)


class EnvironmentReaderTests(SimpleTestCase):
    def test_booleans_accept_common_truthy_values(self):
        for value in ("1", "true", "Yes", "ON"):
            with self.subTest(value=value), patch.dict("os.environ", {"FLAG": value}):
                self.assertIs(read_bool("FLAG"), True)
        with patch.dict("os.environ", {"FLAG": "no"}):
            self.assertIs(read_bool("FLAG", default=True), False)

    def test_lists_are_split_and_trimmed(self):
        with patch.dict("os.environ", {"HOSTS": " a.test, ,b.test "}):
            self.assertEqual(read_list("HOSTS"), ["a.test", "b.test"])

    def test_integers_are_validated(self):
        with patch.dict("os.environ", {"PORT": "8000"}):
            self.assertEqual(read_int("PORT", 1), 8000)
        with patch.dict("os.environ", {"PORT": "eighty"}):
            with self.assertRaisesMessage(ImproperlyConfigured, "PORT"):
                read_int("PORT", 1)

    def test_required_values_must_be_present(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
                read_required("SECRET_KEY")
            with self.assertRaisesMessage(ImproperlyConfigured, "ALLOWED_HOSTS"):
                read_required_list("ALLOWED_HOSTS")
