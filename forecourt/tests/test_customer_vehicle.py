from __future__ import annotations

import unittest


def _normalise(plate_no: str) -> str:
	return plate_no.upper().replace(" ", "") if plate_no else plate_no


class TestCustomerVehicleNormalise(unittest.TestCase):
	def test_uppercase(self) -> None:
		self.assertEqual(_normalise("kda 123a"), "KDA123A")

	def test_spaces_stripped(self) -> None:
		self.assertEqual(_normalise("KDA 123 A"), "KDA123A")

	def test_already_normalised(self) -> None:
		self.assertEqual(_normalise("KDA123A"), "KDA123A")

	def test_empty_plate_unchanged(self) -> None:
		self.assertEqual(_normalise(""), "")


if __name__ == "__main__":
	unittest.main()
