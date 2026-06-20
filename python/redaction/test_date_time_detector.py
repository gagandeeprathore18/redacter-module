import unittest
from redaction.date_time_detector import find_date_time_spans

class TestDateTimeDetector(unittest.TestCase):
    def test_numeric_dates(self):
        text = "Submission Deadline: 07/02/2027 or 7-2-27"
        matches = find_date_time_spans(text)
        # Expected to find both dates
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0][2], "07/02/2027")
        self.assertEqual(matches[1][2], "7-2-27")

    def test_ordinal_dates(self):
        text = "Feedback Release Date: 19th June 2026 or 26th June 2026 or 19th June"
        matches = find_date_time_spans(text)
        self.assertEqual(len(matches), 3)
        self.assertEqual(matches[0][2], "19th June 2026")
        self.assertEqual(matches[1][2], "26th June 2026")
        self.assertEqual(matches[2][2], "19th June")

    def test_month_first_dates(self):
        text = "UPDATED FEBRUARY 17, 2026 or February 17"
        matches = find_date_time_spans(text)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0][2], "FEBRUARY 17, 2026")
        self.assertEqual(matches[1][2], "February 17")

    def test_times(self):
        text = "Submit before 23:59 or 4pm or 5PM or 1600hours or 2:00 pm"
        matches = find_date_time_spans(text)
        self.assertEqual(len(matches), 5)
        self.assertEqual(matches[0][2], "23:59")
        self.assertEqual(matches[1][2], "4pm")
        self.assertEqual(matches[2][2], "5PM")
        self.assertEqual(matches[3][2], "1600hours")
        self.assertEqual(matches[4][2], "2:00 pm")

    def test_merging_spans(self):
        text = "07/02/2027 by 5PM"
        matches = find_date_time_spans(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][2], "07/02/2027 by 5PM")

        text2 = "19th June 2026 at 4pm"
        matches2 = find_date_time_spans(text2)
        self.assertEqual(len(matches2), 1)
        self.assertEqual(matches2[0][2], "19th June 2026 at 4pm")

if __name__ == "__main__":
    unittest.main()
