# Prioritized Improvements & Bugs

Below is the recommended order for tackling improvements and bug fixes. Each item is listed by priority (highest first):

## Telegram Admin Panel Features
**Note:** Admin panel accessible via "🔧 Admin Panel" button (visible only to ADMIN_IDS)

### High Priority - Essential Monitoring & Control
1. **📊 System Status** ✅ COMPLETED
   - Bot uptime and status
   - Active monitoring tasks count
   - Total users count
   - Last check time
   - Redis connection status
   - Database API health
   - Quick stats (items sent today/this week)

2. **👥 User Management**
   - View all users list with their chat_ids ✅ COMPLETED
   - See each user's active monitoring tasks ✅ COMPLETED
   - View user details (task count, last activity) ✅ COMPLETED
   - Broadcast message to all users
   - Broadcast message to specific user
   - Block/unblock users (disable their monitoring)

3. **📋 Task Management**
   - View all monitoring tasks (across all users) ✅ COMPLETED
   - Search tasks by name/URL/chat_id
   - Pause/resume specific task
   - Delete any task
   - View task details (last_updated, last_got_item, items sent count) ✅ COMPLETED
   - See which tasks are most active

4. **🔧 Quick Actions**
   - Force check all tasks now
   - Force check specific user's tasks
   - Clear Redis image cache
   - Restart bot (graceful)
   - View recent errors (last 20) ✅ COMPLETED

### Medium Priority - Operational Features
5. **📈 Statistics & Analytics**
   - Total items found today/week/month
   - Items sent per monitoring task
   - Most active URLs (which produce most results)
   - User activity (who uses bot most)
   - Average check time per URL
   - Failed checks count

6. **⚙️ Configuration Viewer**
   - View current CHECK_FREQUENCY_SECONDS
   - View DB_REMOVE_OLD_ITEMS_DATA_N_DAYS
   - View IMAGE_CACHE_TTL_DAYS
   - View REDIS and DB connection info
   - View bot token (masked)

7. **🧪 Testing Tools**
   - Test URL validator (check if URL is supported)
   - Test URL reachability
   - Send test notification to yourself
   - Test database connection
   - Test Redis connection

8. **📝 Activity Log**
   - Recent notifications sent (last 50)
   - Recent errors (last 50)
   - Recent user actions (task created/deleted)
   - System events log

### Lower Priority - Advanced Features
9. **📊 Advanced Analytics**
   - Chart: Items found per day (last 7 days)
   - Chart: Active users per day
   - Most popular search locations
   - Peak activity hours
   - Average price of monitored items

10. **🔔 Admin Notifications**
    - Auto-notify admin when error rate is high
    - Notify when new user starts using bot
    - Notify when bot restarts ✅ COMPLETED
    - Daily summary report

11. **💾 Backup & Export**
    - Export all tasks to text/CSV format
    - Export user list
    - Export statistics
    - View backup status

12. **🎛️ Advanced Controls**
    - Manually add monitoring for any user
    - Bulk pause/resume tasks
    - Set maintenance mode (disable all checks)
    - Priority mode (check specific tasks more frequently)

## Other Improvements
13. Make custom prompts configurable
    Improves UX after system stability is ensured.
14. Add support for other languages
    Expands user base after core system is robust.
15. Make topn db as a pip package
16. make beter ui (monitorings -> names of monitorings - show status (bot response) -> stop/edit)
