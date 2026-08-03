#!/usr/bin/env python3
"""Quick sanity check that app loads without errors"""
import sys
sys.path.insert(0, 'C:\\Users\\Patrick\\Downloads\\sabong-arena-app')

try:
    import app
    print("App module imports: OK")
    
    import db
    print("DB module imports: OK")
    
    import analytics
    print("Analytics module imports: OK")
    
    # Initialize
    db.init_db()
    print("Database initialized: OK")
    
    # Check route
    with app.app.app_context():
        print("\nChecking routes:")
        for rule in app.app.url_map.iter_rules():
            if 'analytics' in rule.rule or 'dashboard' in rule.rule:
                print(f"  {rule.rule} -> {rule.endpoint}")
    
    print("\nAll checks passed!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
