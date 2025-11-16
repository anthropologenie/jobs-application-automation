"""
Job Application Automation - Scrapers Package

This package contains job scraping and scoring functionality.

Modules:
    - simple_scorer: Job scoring engine with weighted algorithm
    - (future) job_scraper: Web scraping for job boards
    - (future) resume_parser: Resume text extraction
"""

__version__ = "1.0.0"
__author__ = "Karthik Shetty"

from .simple_scorer import SimpleJobScorer

__all__ = ['SimpleJobScorer']
