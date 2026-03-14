#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
import subprocess
import sys
from colorama import Fore, init

# Initialize colorama
init(autoreset=True)

# Setup logging to stdout only (read-only filesystem)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def restart_miner():
    """Restart the twitch miner container"""
    logger.info(f"{Fore.YELLOW}🔄 Restarting twitch-miner container...")
    try:
        result = subprocess.run(
            ['docker', 'restart', 'twitch-miner'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            logger.info(f"{Fore.GREEN}✅ Container restarted successfully")
            return True
        else:
            logger.error(f"{Fore.RED}❌ Failed to restart container: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"{Fore.RED}❌ Error restarting container: {e}")
        return False

def monitor_miner():
    """Monitor the twitch miner and restart on critical errors"""
    logger.info(f"{Fore.CYAN}🚀 Starting Twitch Miner Monitor...")
    
    error_count = 0
    max_errors = 5
    restart_delay = 60  # seconds
    
    while True:
        try:
            # Check for critical errors in the logs
            result = subprocess.run(
                ['docker', 'logs', '--tail=10', 'twitch-miner'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            logs = result.stdout
            
            # Check for critical errors that require restart
            critical_errors = [
                "TypeError: 'NoneType' object is not subscriptable",
                "KeyError: 'data'",
                "HTTPSConnectionPool.*Read timed out"
            ]
            
            has_critical_error = any(error in logs for error in critical_errors)
            
            if has_critical_error:
                error_count += 1
                logger.warning(f"{Fore.YELLOW}⚠️  Critical error detected (count: {error_count}/{max_errors})")
                
                # Show the problematic log lines
                for line in logs.split('\n'):
                    if any(error in line for error in critical_errors):
                        logger.error(f"{Fore.RED}🔴 Error: {line.strip()}")
                
                if error_count >= max_errors:
                    logger.error(f"{Fore.RED}💥 Too many errors ({error_count}), restarting miner...")
                    if restart_miner():
                        error_count = 0
                        logger.info(f"{Fore.GREEN}✅ Waiting {restart_delay}s before monitoring resumes...")
                        time.sleep(restart_delay)
                    else:
                        logger.error(f"{Fore.RED}❌ Failed to restart, will retry in {restart_delay}s...")
                        time.sleep(restart_delay)
            else:
                # Reset error count if no critical errors
                if error_count > 0:
                    logger.info(f"{Fore.GREEN}✅ No critical errors detected, reset error count ({error_count} → 0)")
                    error_count = 0
                
                # Check if miner is running properly
                if "is Online!" in logs:
                    logger.info(f"{Fore.GREEN}✅ Miner is running normally")
                else:
                    logger.warning(f"{Fore.YELLOW}⚠️  Miner might not be fully operational")
            
            # Wait before next check
            time.sleep(30)
            
        except subprocess.TimeoutExpired:
            logger.error(f"{Fore.RED}❌ Timeout checking miner logs")
            error_count += 1
        except Exception as e:
            logger.error(f"{Fore.RED}❌ Unexpected error in monitor: {e}")
            error_count += 1
        
        # Safety: if too many monitor errors, restart anyway
        if error_count >= max_errors * 2:
            logger.error(f"{Fore.RED}💥 Too many monitor errors, forcing restart...")
            restart_miner()
            error_count = 0

if __name__ == "__main__":
    try:
        monitor_miner()
    except KeyboardInterrupt:
        logger.info(f"{Fore.YELLOW}👋 Monitor stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"{Fore.RED}💥 Fatal error in monitor: {e}")
        sys.exit(1)
