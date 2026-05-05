from scrapers.base import BaseScraper
from scrapers.leboncoin import LeBonCoinScraper
from scrapers.lacentrale import LaCentraleScraper
from scrapers.facebook import FacebookScraper
from scrapers.paruvendu import ParuVenduScraper
from scrapers.autoscout24 import AutoScout24Scraper
from scrapers.ouestfrance import OuestFranceScraper
from scrapers.caradisiac import CaradisiacScraper
from scrapers.leparking import LeParkingScraper
from scrapers.autoreflex import AutoReflexScraper
from scrapers.largus import LargusScraper

ALL_SCRAPERS: list[type[BaseScraper]] = [
    LeBonCoinScraper,
    LaCentraleScraper,
    FacebookScraper,
    ParuVenduScraper,
    AutoScout24Scraper,
    OuestFranceScraper,
    CaradisiacScraper,
    LeParkingScraper,
    AutoReflexScraper,
    LargusScraper,
]
