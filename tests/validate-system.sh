echo ""
  echo "1️⃣ Checking Database..."
  TABLES=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
  SCRAPED=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM scraped_jobs;")
  echo "   ✅ Tables: $TABLES | Scraped Jobs: $SCRAPED"

  echo ""
  echo "2️⃣ Checking API Server..."
  if curl -s "http://localhost:8081/api/metrics" > /dev/null 2>&1; then
      echo "   ✅ API Server responding on port 8081"
  else
      echo "   ❌ API Server not responding!"
  fi

  echo ""
  echo "3️⃣ Checking Dashboard..."
  if curl -s "http://localhost:8082/" > /dev/null 2>&1; then
      echo "   ✅ Dashboard responding on port 8082"
  else
      echo "   ❌ Dashboard not responding!"
  fi

  echo ""
  echo "4️⃣ Testing Scraped Jobs API..."
  STATS=$(curl -s "http://localhost:8081/api/scraped-jobs/stats" | python3 -c "import sys, json; data=json.load(sys.stdin);
  print(data['success'])" 2>/dev/null)
  if [ "$STATS" = "True" ]; then
      echo "   ✅ Scraped jobs API working"
  else
      echo "   ❌ Scraped jobs API failed!"
  fi

  echo ""
  echo "5️⃣ Performance Check..."
  API_TIME=$(curl -s -o /dev/null -w "%{time_total}" "http://localhost:8081/api/scraped-jobs/stats")
  echo "   ✅ API response time: ${API_TIME}s"

  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║                    ✅ VALIDATION COMPLETE                   ║"
  echo "╚════════════════════════════════════════════════════════════╝"
  echo ""
  echo "🌐 Access URLs:"
  echo "   Dashboard: http://localhost:8082"
  echo "   API Docs:  http://localhost:8081/api/metrics"
  echo ""
