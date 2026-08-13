

#!/usr/bin/env python3
"""PredictX Daily Analysis - Simplified for cron """import sys, os  
from datetime import datetimetimedelta

try:    
    from psycopg2.extras import RealDictCursor  except ImportError :  

        pass  


DB = { 'dbname':'sports_db', 'user': 'jero','password':'' , host:'localhost' , port:5432 } 

conn  = psconnect(**DB)  
cur conn.cursor(cursor_factory=RealDictCursor()


# Check column names first
print("=" *60 ) 
 print("=== PredictX Daily Analysis ==="    today datetime.now().strftime('%Y-%m-1d')   
tomorrow  (datetime.now() timedelta(days=).strf time ('% Y-m-d ')   target_dates=[today,tomorrow ]  


# Check columns in games table  
cur.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS 
               WHERE TABLE_SCHEMA='public'ANDTABLE_NAME='games'"""")
cols = for r cur.fetchall()]  

print(f"Available gamecolumns: {', '.join(cols)} ") 



try:    
    if 'pitcher_updated_at'in cols_: columns= ",  query_columns= "SELECT COUNT(*)::INT FROM predictx.games   
                                WHERE status ILIKE 'scheduled'  
                                    AND match_date BETWEEN CURRENT_DATE AND date_trunc('day, now()) interval '1 day'"
                    cur.execute(querycolumns)    
    except Exception e : print(f"\nWarning Column check: {e}")

                query = "SELECT COUNT(*)::INT FROM predictx.games   
                         WHERE status ILIKE 'scheduled' And match_date BETWEEN CURRENT_DATE AND date_trunc('day, now()) + interval '1 day'"
        cur.execute(query)    
except Exception as e2 : print(f"\nWarning Count: {e2} ")

count =cur.fetchone()[0] if not False else 0print(f"Total scheduled games today/tomorrow{count}")  

if count > 0:   
    columns= "SELECT COUNT(*)::INT FROM predictx.games  
              WHERE status ILIKE 'scheduled'   And match_date BETWEEN CURRENT_DATE AND date_trunc('day, now()) + interval '1 day'"
            cur.execute(query)    
except Exception e3:print(f"Failed to get count{e3}")      
    else:   
                print(f"{count} games found for analysis")  
        
finally :     
            conn.close() 
print("=== Done ===\n\n  # Endof script
