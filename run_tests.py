#!/usr/bin/env python3
"""
Test runner script for YT-to-Jellyfin
"""
import os
import sys
import unittest
import argparse

def run_tests(test_type=None):
    """Run the specified tests"""
    # Get the directory containing the tests
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    
    # Create a test loader
    loader = unittest.TestLoader()
    
    # Discover tests based on the type
    if test_type == "api":
        suite = loader.discover(test_dir, pattern="test_api.py")
    elif test_type == "basic":
        suite = loader.discover(test_dir, pattern="test_basic.py")
    elif test_type == "integration":
        suite = loader.discover(test_dir, pattern="test_integration.py")
    elif test_type == "job":
        suite = loader.discover(test_dir, pattern="test_job_management.py")
    elif test_type == "web":
        web_dir = os.path.join(test_dir, 'web')
        suite = loader.discover(web_dir, pattern="test_*.py")
    else:
        # Run all tests except web tests (which require webdriver)
        suite = unittest.TestSuite()
        basic_suite = loader.discover(test_dir, pattern="test_basic.py")
        api_suite = loader.discover(test_dir, pattern="test_api.py")
        job_suite = loader.discover(test_dir, pattern="test_job_management.py")
        integration_suite = loader.discover(test_dir, pattern="test_integration.py")
        
        suite.addTests(basic_suite)
        suite.addTests(api_suite)
        suite.addTests(job_suite)
        suite.addTests(integration_suite)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return 0 if all tests passed, 1 otherwise
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run tests for YT-to-Jellyfin')
    parser.add_argument('--type', choices=['basic', 'api', 'job', 'integration', 'web', 'all'],
                        help='Type of tests to run', default='all')
    
    args = parser.parse_args()
    sys.exit(run_tests(args.type))