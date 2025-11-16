#!/usr/bin/env python3
"""
Simple Job Scorer - AI-Powered Job Matching Engine

This module implements a scoring algorithm to evaluate job postings against
a resume configuration file. It calculates match scores based on skills,
experience, domains, location, and red flags.

Author: Karthik Shetty
Created: 2025-11-14
"""

import json
import re
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleJobScorer:
    """
    Job scoring engine that evaluates job postings against resume configuration.

    Uses a weighted scoring algorithm:
    - Skills Match: 40%
    - Experience Match: 20%
    - Domain Match: 20%
    - Location Match: 10%
    - Red Flags: 10% (negative)
    """

    def __init__(self, config_path: str = "data/resume_config.json"):
        """
        Initialize the job scorer with configuration.

        Args:
            config_path: Path to resume configuration JSON file

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is malformed
        """
        logger.info(f"Loading configuration from {config_path}")

        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please ensure {config_path} exists."
            )

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Malformed JSON in {config_path}: {e.msg}",
                e.doc,
                e.pos
            )

        # Parse configuration sections
        self._parse_config()
        logger.info("Configuration loaded successfully")

    def _parse_config(self) -> None:
        """Parse and structure configuration data for efficient access."""
        # Combine all skills into a single dictionary with weights
        self.all_skills = {}

        for category in ['critical', 'high_value', 'nice_to_have']:
            items = self.config['skills'][category]['items']
            self.all_skills.update(items)

        # Parse red flags
        self.red_flags = {}
        for category in ['deal_breakers', 'consultancy_signals',
                         'manual_testing_only', 'outdated_tech']:
            if category in self.config['red_flags']:
                items = self.config['red_flags'][category].get('items', {})
                self.red_flags.update(items)

        # Parse domains
        self.domains = self.config['domains']['items']

        # Parse scoring weights
        self.weights = self.config['scoring_weights']

        # Resume profile
        self.profile = self.config['profile']

        # Thresholds
        self.auto_import_threshold = self.config['auto_import_threshold']

        logger.debug(f"Loaded {len(self.all_skills)} skills, "
                    f"{len(self.red_flags)} red flags, "
                    f"{len(self.domains)} domains")

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for matching.

        Args:
            text: Raw text to normalize

        Returns:
            Lowercase text with extra whitespace stripped
        """
        if not text:
            return ""
        return " ".join(text.lower().strip().split())

    def calculate_skills_score(self, job_text: str) -> Tuple[float, List[Dict[str, any]]]:
        """
        Calculate skills match score.

        Args:
            job_text: Normalized job description text

        Returns:
            Tuple of (normalized_score, list of matched skills)
            - normalized_score: 0-100 scale
            - matched_skills: List of dicts with skill name and weight
        """
        matched_skills = []
        total_weight = 0

        job_text = self.normalize_text(job_text)

        for skill, weight in self.all_skills.items():
            # Create regex pattern with word boundaries
            # Handle special characters in skill names
            skill_pattern = re.escape(skill.lower())
            pattern = r'\b' + skill_pattern + r'\b'

            if re.search(pattern, job_text):
                matched_skills.append({
                    'skill': skill,
                    'weight': weight
                })
                total_weight += weight

        # Sort by weight descending
        matched_skills.sort(key=lambda x: x['weight'], reverse=True)

        # Normalize to 0-100 scale
        # Assume max possible skills score is sum of top 10 critical skills (10*10=100)
        max_possible_score = 100
        normalized_score = min(100, (total_weight / max_possible_score) * 100)

        logger.debug(f"Skills matched: {len(matched_skills)}, "
                    f"Total weight: {total_weight}, "
                    f"Normalized: {normalized_score:.1f}")

        return normalized_score, matched_skills

    def calculate_red_flags(self, job_text: str) -> Tuple[float, List[Dict[str, any]]]:
        """
        Calculate red flag penalties.

        Args:
            job_text: Normalized job description text

        Returns:
            Tuple of (total_penalty, list of red flags found)
            - total_penalty: Negative number (penalties)
            - red_flags_found: List of dicts with flag name and penalty
        """
        red_flags_found = []
        total_penalty = 0

        job_text = self.normalize_text(job_text)

        for flag, penalty in self.red_flags.items():
            # Create regex pattern with word boundaries
            flag_pattern = re.escape(flag.lower())
            pattern = r'\b' + flag_pattern + r'\b'

            if re.search(pattern, job_text):
                red_flags_found.append({
                    'flag': flag,
                    'penalty': penalty
                })
                total_penalty += penalty

        # Cap penalty at -50 to avoid extreme negatives
        total_penalty = max(total_penalty, -50)

        logger.debug(f"Red flags found: {len(red_flags_found)}, "
                    f"Total penalty: {total_penalty}")

        return total_penalty, red_flags_found

    def calculate_domain_score(self, job_text: str) -> Tuple[float, List[Dict[str, any]]]:
        """
        Calculate domain match score.

        Args:
            job_text: Normalized job description text

        Returns:
            Tuple of (normalized_score, list of matched domains)
            - normalized_score: 0-100 scale
            - matched_domains: List of dicts with domain name and weight
        """
        matched_domains = []
        total_weight = 0

        job_text = self.normalize_text(job_text)

        for domain, weight in self.domains.items():
            # Create flexible pattern for domain matching
            # Handle domain variations (e.g., "ETL/DWH" vs "ETL" or "DWH")
            domain_lower = domain.lower()

            # Split on / to check individual parts
            domain_parts = [part.strip() for part in re.split(r'[/,]', domain_lower)]

            matched = False
            for part in domain_parts:
                if len(part) > 2:  # Skip very short parts
                    pattern = r'\b' + re.escape(part) + r'\b'
                    if re.search(pattern, job_text):
                        matched = True
                        break

            if matched:
                matched_domains.append({
                    'domain': domain,
                    'weight': weight
                })
                total_weight += weight

        # Sort by weight descending
        matched_domains.sort(key=lambda x: x['weight'], reverse=True)

        # Normalize to 0-100 scale
        # Assume max possible domain score is sum of top 6 domains (6*8=48, round to 50)
        max_possible_score = 50
        normalized_score = min(100, (total_weight / max_possible_score) * 100)

        logger.debug(f"Domains matched: {len(matched_domains)}, "
                    f"Total weight: {total_weight}, "
                    f"Normalized: {normalized_score:.1f}")

        return normalized_score, matched_domains

    def calculate_location_score(self, location: str) -> float:
        """
        Calculate location match score.

        Args:
            location: Job location string

        Returns:
            Score from 0-100
        """
        if not location:
            return 50  # Neutral if location not specified

        location = self.normalize_text(location)

        # Check for remote indicators
        remote_keywords = ['remote', 'anywhere', 'work from home', 'wfh']
        if any(keyword in location for keyword in remote_keywords):
            return 100

        # Check for hybrid
        if 'hybrid' in location:
            return 50

        # Check for preferred locations from config
        preferred_locations = self.config.get('filters', {}).get('location_keywords', {}).get('acceptable', [])
        for pref_loc in preferred_locations:
            if pref_loc.lower() in location:
                return 30

        # Onsite or other
        return 0

    def calculate_experience_score(self, years_required: str, resume_years: int) -> float:
        """
        Calculate experience match score.

        Args:
            years_required: Experience requirement string (e.g., "5-8 years", "3+ years")
            resume_years: Years of experience from resume

        Returns:
            Score from 0-100
        """
        if not years_required:
            return 100  # No requirement specified

        years_required = self.normalize_text(years_required)

        # Extract numbers from requirement string
        numbers = re.findall(r'\d+', years_required)

        if not numbers:
            return 100  # Cannot parse requirement

        if len(numbers) == 1:
            # Single number like "5+ years" or "5 years"
            required = int(numbers[0])

            if '+' in years_required or 'plus' in years_required or 'more' in years_required:
                # Minimum requirement
                if resume_years >= required:
                    return 100
                elif resume_years >= required - 1:
                    return 80
                else:
                    return 50
            else:
                # Exact requirement
                if resume_years == required:
                    return 100
                elif abs(resume_years - required) <= 1:
                    return 90
                elif abs(resume_years - required) <= 2:
                    return 70
                else:
                    return 50

        else:
            # Range like "5-8 years"
            min_years = int(numbers[0])
            max_years = int(numbers[1])

            if min_years <= resume_years <= max_years:
                return 100  # Perfect fit
            elif resume_years > max_years:
                # Over-qualified
                if resume_years - max_years <= 2:
                    return 80
                else:
                    return 60
            else:
                # Under-qualified
                if min_years - resume_years <= 1:
                    return 70
                else:
                    return 40

    def score_job(self, job_data: Dict) -> Dict:
        """
        Score a job posting using weighted algorithm.

        Args:
            job_data: Dictionary with keys:
                - title (required): Job title
                - description (required): Job description
                - location (optional): Job location
                - company (optional): Company name
                - tags (optional): Comma-separated tags
                - experience_required (optional): Experience requirement

        Returns:
            Dictionary with complete scoring breakdown

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        if 'title' not in job_data or 'description' not in job_data:
            raise ValueError("job_data must contain 'title' and 'description' fields")

        # Combine all text fields for analysis
        full_text = " ".join([
            job_data.get('title', ''),
            job_data.get('description', ''),
            job_data.get('tags', ''),
            job_data.get('company', '')
        ])

        # Calculate component scores
        skills_score, matched_skills = self.calculate_skills_score(full_text)
        red_flag_penalty, red_flags_found = self.calculate_red_flags(full_text)
        domain_score, matched_domains = self.calculate_domain_score(full_text)
        location_score = self.calculate_location_score(job_data.get('location', ''))
        experience_score = self.calculate_experience_score(
            job_data.get('experience_required', ''),
            self.profile['years_experience']
        )

        # Apply weights and calculate final score
        final_score = (
            (skills_score * self.weights['skills_match']) +
            (experience_score * self.weights['experience_match']) +
            (domain_score * self.weights['domain_match']) +
            (location_score * self.weights['location_match']) +
            (red_flag_penalty * self.weights['red_flags'])
        )

        # Clamp between 0-100
        final_score = max(0, min(100, final_score))

        # Classify job
        if final_score >= 85:
            classification = "EXCELLENT"
        elif final_score >= 75:
            classification = "HIGH_FIT"
        elif final_score >= 65:
            classification = "MEDIUM_FIT"
        elif final_score >= 40:
            classification = "LOW_FIT"
        else:
            classification = "NO_FIT"

        # Generate recommendation
        recommendation = self._get_recommendation(final_score, classification)

        # Build result
        result = {
            'final_score': round(final_score, 2),
            'classification': classification,
            'recommendation': recommendation,
            'breakdown': {
                'skills_score': round(skills_score, 2),
                'experience_score': round(experience_score, 2),
                'domain_score': round(domain_score, 2),
                'location_score': round(location_score, 2),
                'red_flag_penalty': round(red_flag_penalty, 2)
            },
            'matched_skills': matched_skills[:10],  # Top 10
            'matched_domains': matched_domains[:5],  # Top 5
            'red_flags': red_flags_found,
            'job_info': {
                'title': job_data.get('title', 'N/A'),
                'company': job_data.get('company', 'N/A'),
                'location': job_data.get('location', 'N/A')
            },
            'should_auto_import': final_score >= self.auto_import_threshold
        }

        logger.info(f"Scored job '{job_data.get('title')}': "
                   f"{final_score:.1f} ({classification})")

        return result

    def _get_recommendation(self, score: float, classification: str) -> str:
        """
        Generate actionable recommendation based on score.

        Args:
            score: Final job score (0-100)
            classification: Job classification

        Returns:
            Recommendation string with emoji and action
        """
        recommendations = {
            "EXCELLENT": f"🎯 APPLY IMMEDIATELY - Outstanding match ({score:.1f}%)",
            "HIGH_FIT": f"✅ STRONG CANDIDATE - Apply today ({score:.1f}%)",
            "MEDIUM_FIT": f"⚠️ REVIEW CAREFULLY - Consider applying ({score:.1f}%)",
            "LOW_FIT": f"❌ WEAK MATCH - Likely not worth time ({score:.1f}%)",
            "NO_FIT": f"🚫 SKIP - Poor fit ({score:.1f}%)"
        }
        return recommendations.get(classification, f"Unknown classification ({score:.1f}%)")


def print_job_score(result: Dict) -> None:
    """
    Pretty print job scoring results.

    Args:
        result: Result dictionary from score_job()
    """
    print("\n" + "="*70)
    print(f"📋 JOB: {result['job_info']['title']}")
    print(f"🏢 COMPANY: {result['job_info']['company']}")
    print(f"📍 LOCATION: {result['job_info']['location']}")
    print("="*70)

    print(f"\n🎯 FINAL SCORE: {result['final_score']:.1f}/100")
    print(f"📊 CLASSIFICATION: {result['classification']}")
    print(f"💡 RECOMMENDATION: {result['recommendation']}")

    if result['should_auto_import']:
        print(f"✅ AUTO-IMPORT: YES (threshold: auto-import)")
    else:
        print(f"❌ AUTO-IMPORT: NO")

    print(f"\n📈 SCORE BREAKDOWN:")
    print(f"   Skills Match:      {result['breakdown']['skills_score']:6.2f}/100 (weight: 40%)")
    print(f"   Experience Match:  {result['breakdown']['experience_score']:6.2f}/100 (weight: 20%)")
    print(f"   Domain Match:      {result['breakdown']['domain_score']:6.2f}/100 (weight: 20%)")
    print(f"   Location Match:    {result['breakdown']['location_score']:6.2f}/100 (weight: 10%)")
    print(f"   Red Flag Penalty:  {result['breakdown']['red_flag_penalty']:6.2f} (weight: 10%)")

    print(f"\n🔧 TOP MATCHED SKILLS ({len(result['matched_skills'])}):")
    for i, skill in enumerate(result['matched_skills'][:5], 1):
        print(f"   {i}. {skill['skill']} (weight: {skill['weight']})")

    if len(result['matched_skills']) > 5:
        print(f"   ... and {len(result['matched_skills']) - 5} more")

    print(f"\n🎓 MATCHED DOMAINS ({len(result['matched_domains'])}):")
    if result['matched_domains']:
        for i, domain in enumerate(result['matched_domains'][:3], 1):
            print(f"   {i}. {domain['domain']} (weight: {domain['weight']})")
    else:
        print("   None")

    print(f"\n🚫 RED FLAGS ({len(result['red_flags'])}):")
    if result['red_flags']:
        for i, flag in enumerate(result['red_flags'], 1):
            print(f"   {i}. {flag['flag']} (penalty: {flag['penalty']})")
    else:
        print("   None ✅")

    print("\n" + "="*70)


if __name__ == "__main__":
    """Test the scoring engine with sample jobs."""

    print("\n" + "="*70)
    print("🧪 JOB SCORING ENGINE - TEST SUITE")
    print("="*70)

    try:
        # Initialize scorer
        scorer = SimpleJobScorer(config_path="data/resume_config.json")
        print(f"\n✅ Scorer initialized successfully")
        print(f"   Profile: {scorer.profile['name']}")
        print(f"   Experience: {scorer.profile['years_experience']} years")
        print(f"   Min Salary: ₹{scorer.profile['min_salary_inr']:,}")
        print(f"   Auto-import threshold: {scorer.auto_import_threshold}%")

        # Test Case 1: Excellent Data QA Job
        print("\n" + "🔴"*35)
        print("TEST CASE 1: EXCELLENT DATA QA JOB (Expected: 80-90 score)")
        print("🔴"*35)

        job1 = {
            'title': 'Senior Data QA Engineer',
            'description': 'We need a Data QA Engineer to validate ETL pipelines, test Snowflake data warehouse, write SQL queries for data validation, and automate testing with Python and Pytest. Experience with AWS, data quality, and test automation required. This is for our AI/ML analytics platform.',
            'location': 'Remote',
            'company': 'DataTech AI',
            'tags': 'SQL, Python, AWS, ETL, Snowflake, Data Quality',
            'experience_required': '5-8 years'
        }

        result1 = scorer.score_job(job1)
        print_job_score(result1)

        # Test Case 2: Frontend Job (Should Score Low)
        print("\n" + "🟡"*35)
        print("TEST CASE 2: FRONTEND JOB (Expected: <30 score, red flags)")
        print("🟡"*35)

        job2 = {
            'title': 'QA Engineer - React Testing',
            'description': 'Looking for QA Engineer to test React web application using Cypress. Strong JavaScript, TypeScript, and frontend testing required. Manual testing and UI automation skills essential.',
            'location': 'Hybrid - Bangalore',
            'company': 'WebApp Startup',
            'tags': 'Cypress, React, JavaScript, UI Testing',
            'experience_required': '3-5 years'
        }

        result2 = scorer.score_job(job2)
        print_job_score(result2)

        # Test Case 3: Consultancy Role (Should Score Low)
        print("\n" + "🟢"*35)
        print("TEST CASE 3: CONSULTANCY ROLE (Expected: <20 score, heavy penalties)")
        print("🟢"*35)

        job3 = {
            'title': 'QA Engineer - Client Placement',
            'description': 'We are hiring QA Engineers for third party client placement. Multiple client projects. Bench sales position. Will work at client location.',
            'location': 'Multiple Locations',
            'company': 'TechStaffing Corp',
            'tags': 'QA, Testing, Manual, Automation',
            'experience_required': '2-10 years'
        }

        result3 = scorer.score_job(job3)
        print_job_score(result3)

        # Summary
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        print(f"Test 1 (Data QA):     {result1['final_score']:.1f}/100 - {result1['classification']}")
        print(f"Test 2 (Frontend):    {result2['final_score']:.1f}/100 - {result2['classification']}")
        print(f"Test 3 (Consultancy): {result3['final_score']:.1f}/100 - {result3['classification']}")
        print("="*70)

        print("\n✅ All tests completed successfully!")

    except FileNotFoundError as e:
        logger.error(f"Configuration file error: {e}")
        print(f"\n❌ ERROR: {e}")
        print("Please ensure data/resume_config.json exists.")

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        print(f"\n❌ ERROR: Invalid JSON in configuration file")
        print(f"   {e}")

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ UNEXPECTED ERROR: {e}")
