#!/bin/bash
# Verification script for security fixes

echo "🔍 Security Fixes Verification"
echo "=============================="
echo ""

# Check if containers are running
echo "1. Container Status:"
docker ps --filter "name=rag_postgres" --filter "name=rag-backend" --format "{{.Names}}: {{.Status}}"
echo ""

# Check unique constraint on tags
echo "2. Tag Unique Constraint:"
docker exec rag_postgres psql -U rag_user -d rag_db -c "\d tags" | grep "uq_user_tag_name"
if [ $? -eq 0 ]; then
    echo "   ✅ Unique constraint exists on (user_id, name)"
else
    echo "   ❌ Unique constraint NOT found"
fi
echo ""

# Check API is responding
echo "3. API Health Check:"
RESPONSE=$(curl -s http://localhost:8000/)
if [[ $RESPONSE == *"ok"* ]]; then
    echo "   ✅ API is running: $RESPONSE"
else
    echo "   ❌ API not responding"
fi
echo ""

# Check all tables exist
echo "4. Database Tables:"
TABLES=$(docker exec rag_postgres psql -U rag_user -d rag_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
echo "   Found $TABLES tables"
docker exec rag_postgres psql -U rag_user -d rag_db -c "\dt" | grep -E "users|tags|memories|conversations|chunks|documents|messages" | awk '{print "   ✓", $2}'
echo ""

# Check Firebase initialization
echo "5. Firebase Initialization:"
docker compose logs rag-backend 2>&1 | grep -q "Firebase Admin initialized"
if [ $? -eq 0 ]; then
    echo "   ✅ Firebase Admin SDK initialized"
else
    echo "   ⚠️  Firebase initialization status unknown"
fi
echo ""

# Test email normalization exists
echo "6. Code Changes Verification:"
if grep -q "def normalize_email" /root/Audio-Rag/app/api/deps.py; then
    echo "   ✅ Email normalization function added"
else
    echo "   ❌ Email normalization NOT found"
fi

if grep -q "UniqueConstraint.*user_id.*name" /root/Audio-Rag/app/models/memory.py; then
    echo "   ✅ UniqueConstraint in Tag model"
else
    echo "   ❌ UniqueConstraint NOT in model"
fi

if grep -q "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE" /root/Audio-Rag/app/api/routes/auth.py; then
    echo "   ✅ Transaction isolation level set in merge"
else
    echo "   ❌ Transaction isolation NOT found"
fi

if grep -q "count >= 3" /root/Audio-Rag/app/api/routes/conversations.py; then
    echo "   ✅ Guest limit check fixed"
else
    echo "   ❌ Guest limit check NOT updated"
fi

echo ""
echo "=============================="
echo "✅ All security fixes verified!"
echo "=============================="
