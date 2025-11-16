#!/usr/bin/env python3
"""
Example usage of SimpleJobScorer

This script demonstrates how to use the job scoring engine programmatically.
"""

from simple_scorer import SimpleJobScorer, print_job_score


def main():
    """Demonstrate scorer usage with real-world examples."""

    print("="*70)
    print("🎯 SimpleJobScorer - Example Usage")
    print("="*70)

    # Initialize the scorer
    print("\n1️⃣ Initializing scorer...")
    scorer = SimpleJobScorer(config_path="../data/resume_config.json")
    print(f"✅ Loaded configuration for {scorer.profile['name']}")
    print(f"   Experience: {scorer.profile['years_experience']} years")
    print(f"   Loaded {len(scorer.all_skills)} skills, "
          f"{len(scorer.red_flags)} red flags, "
          f"{len(scorer.domains)} domains")

    # Example 1: Score a single job
    print("\n2️⃣ Scoring a single job...")
    job = {
        'title': 'Data Quality Engineer',
        'description': '''
            Join our team as a Data Quality Engineer! You will:
            - Write SQL queries to validate data in Snowflake
            - Build Python automation for ETL testing
            - Ensure data quality in our analytics platform
            - Work with AWS services (S3, Glue, Redshift)
            - Collaborate with data engineers on pipeline testing

            Requirements:
            - 5-7 years of experience in QA or Data Engineering
            - Strong SQL and Python skills
            - Experience with data warehouses (Snowflake, Redshift)
            - Test automation experience
            - AWS cloud experience
        ''',
        'location': 'Remote - US/India',
        'company': 'CloudData Inc.',
        'tags': 'SQL, Python, AWS, Snowflake, ETL, Data Quality',
        'experience_required': '5-7 years'
    }

    result = scorer.score_job(job)
    print_job_score(result)

    # Example 2: Batch scoring multiple jobs
    print("\n3️⃣ Batch scoring multiple jobs...")

    jobs = [
        {
            'title': 'Senior QA Engineer - Analytics',
            'description': 'Test BI dashboards, SQL validation, data testing',
            'location': 'Remote',
            'company': 'Analytics Corp',
            'experience_required': '6-8 years'
        },
        {
            'title': 'Automation Engineer',
            'description': 'Selenium WebDriver, UI testing, manual testing',
            'location': 'Bangalore - Onsite',
            'company': 'TestingSoft',
            'experience_required': '4-6 years'
        },
        {
            'title': 'QA Lead - Data Platform',
            'description': 'Lead data QA team, ETL testing, BigQuery, Python, AWS',
            'location': 'Remote',
            'company': 'DataPlatform.io',
            'experience_required': '7-10 years'
        }
    ]

    print(f"\nScoring {len(jobs)} jobs...\n")
    results = []
    for job in jobs:
        result = scorer.score_job(job)
        results.append(result)
        print(f"  {result['final_score']:5.1f} | "
              f"{result['classification']:12s} | "
              f"{job['title'][:40]}")

    # Example 3: Filter and sort by score
    print("\n4️⃣ Filtering high-fit jobs (score >= 75)...")
    high_fit = [r for r in results if r['final_score'] >= 75]

    if high_fit:
        print(f"\n✅ Found {len(high_fit)} high-fit job(s):")
        for r in high_fit:
            print(f"   - {r['job_info']['title']} at {r['job_info']['company']}")
            print(f"     Score: {r['final_score']:.1f} | {r['recommendation']}")
    else:
        print("❌ No high-fit jobs found in this batch")

    # Example 4: Analyze scoring components
    print("\n5️⃣ Analyzing scoring breakdown for best match...")
    best_match = max(results, key=lambda x: x['final_score'])

    print(f"\nBest Match: {best_match['job_info']['title']}")
    print(f"Final Score: {best_match['final_score']:.1f}/100\n")

    print("Component Scores:")
    for component, score in best_match['breakdown'].items():
        bar_length = int(score / 2) if score > 0 else 0
        bar = "█" * bar_length
        print(f"  {component:20s} {score:6.1f} | {bar}")

    print(f"\nTop Skills Matched:")
    for skill in best_match['matched_skills'][:3]:
        print(f"  ✓ {skill['skill']} (weight: {skill['weight']})")

    # Example 5: Check for red flags
    print("\n6️⃣ Checking for jobs with red flags...")
    jobs_with_flags = [r for r in results if r['red_flags']]

    if jobs_with_flags:
        print(f"\n⚠️ Found {len(jobs_with_flags)} job(s) with red flags:")
        for r in jobs_with_flags:
            print(f"\n   {r['job_info']['title']}")
            for flag in r['red_flags'][:3]:
                print(f"     🚫 {flag['flag']} (penalty: {flag['penalty']})")
    else:
        print("✅ No red flags found in any jobs")

    # Example 6: Export results
    print("\n7️⃣ Exporting results to JSON...")
    import json
    output = {
        'scored_jobs': [
            {
                'title': r['job_info']['title'],
                'company': r['job_info']['company'],
                'score': r['final_score'],
                'classification': r['classification'],
                'auto_import': r['should_auto_import']
            }
            for r in results
        ],
        'summary': {
            'total_jobs': len(results),
            'high_fit': len([r for r in results if r['classification'] == 'HIGH_FIT']),
            'medium_fit': len([r for r in results if r['classification'] == 'MEDIUM_FIT']),
            'low_fit': len([r for r in results if r['classification'] == 'LOW_FIT']),
            'no_fit': len([r for r in results if r['classification'] == 'NO_FIT']),
        }
    }

    # Uncomment to save to file:
    # with open('scored_jobs.json', 'w') as f:
    #     json.dump(output, f, indent=2)

    print("✅ Results exported:")
    print(json.dumps(output, indent=2))

    print("\n" + "="*70)
    print("✅ Example completed successfully!")
    print("="*70)


if __name__ == "__main__":
    main()
