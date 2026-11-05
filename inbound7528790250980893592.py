
import hashlib
import hmac
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).with_name('smart_inventory_data.json')

DEMO_ACCOUNTS = [
    ('jose.rizal', 'Jose Rizal', 'Administrator', 'Rizal@2026!'),
    ('andres.bonifacio', 'Andres Bonifacio', 'Administrator', 'Bonifacio@2026!'),
    ('maria.clara', 'Maria Clara', 'Staff', 'MariaClara@2026!'),
    ('juan.luna', 'Juan Luna', 'Staff', 'JuanLuna@2026!'),
    ('emilio.jacinto', 'Emilio Jacinto', 'Staff', 'Jacinto@2026!'),
    ('apolinario.mabini', 'Apolinario Mabini', 'Staff', 'Mabini@2026!'),
]
DEMO_PASSWORD_VERSION = 1
STARTER_INVENTORY_VERSION = 1

STARTER_ITEMS = [
    (101, 'Bond Paper (A4)', 'School Supplies', 100, 250, 20),
    (102, 'Notebook', 'School Supplies', 80, 35, 20),
    (103, 'Folder', 'School Supplies', 50, 15, 15),
    (104, 'Ballpen', 'Writing Materials', 150, 12, 30),
    (105, 'Pencil', 'Writing Materials', 100, 8, 25),
    (106, 'Whiteboard Marker', 'Writing Materials', 20, 45, 30),
    (107, 'Keyboard', 'IT Equipment', 15, 450, 5),
    (108, 'Mouse', 'IT Equipment', 20, 250, 5),
    (109, 'Monitor', 'IT Equipment', 8, 4500, 3),
    (110, 'Broom', 'Cleaning Supplies', 30, 85, 10),
    (111, 'Mop', 'Cleaning Supplies', 12, 180, 5),
    (112, 'Trash Bags', 'Cleaning Supplies', 15, 65, 20),
    (113, 'Stapler', 'Office Equipment', 25, 120, 10),
    (114, 'Scissors', 'Office Equipment', 20, 75, 5),
    (115, 'Whiteboard Eraser', 'Classroom Equipment', 10, 50, 15),
]

def starter_inventory():
    return [dict(zip(('id', 'name', 'category', 'quantity', 'unit_price', 'reorder_level'), item))
            for item in STARTER_ITEMS]

def normalize_item(item):
    """Convert older list-based records into the current dictionary format."""
    if isinstance(item, (list, tuple)) and len(item) == 6:
        item = dict(zip(('id', 'name', 'category', 'quantity', 'unit_price', 'reorder_level'), item))
    if not isinstance(item, dict):
        raise ValueError('Inventory item must be a six-field list or dictionary')
    keys = ('id', 'name', 'category', 'quantity', 'unit_price', 'reorder_level')
    if any(k not in item for k in keys):
        raise ValueError('Inventory record is missing required fields')
    return {
        'id': int(item['id']), 'name': str(item['name']).strip(),
        'category': str(item['category']).strip(),
        'quantity': int(item['quantity']), 'unit_price': float(item['unit_price']),
        'reorder_level': int(item['reorder_level']),
    }

def normalize_inventory(items):
    converted = [normalize_item(item) for item in items]
    if any(i['id'] <= 0 or i['quantity'] < 0 or i['reorder_level'] < 0 or
           not i['name'] or not i['category'] or not (0 <= i['unit_price'] < float('inf'))
           for i in converted):
        raise ValueError('Inventory contains invalid item values')
    ids = [i['id'] for i in converted]
    if len(ids) != len(set(ids)):
        raise ValueError('Inventory contains duplicate Item IDs')
    return converted

def password_hash(password, salt=None):
    salt = salt if salt is not None else os.urandom(16)
    result = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 250000)
    return {'salt': salt.hex(), 'hash': result.hex()}

def valid_password(password, record):
    try:
        candidate = password_hash(password, bytes.fromhex(record['salt']))['hash']
        return hmac.compare_digest(candidate, record['hash'])
    except (KeyError, ValueError, TypeError):
        return False

def load_data():
    if not DATA_FILE.exists():
        users = {
            username: {'name': name, 'role': role, **password_hash(password)}
            for username, name, role, password in DEMO_ACCOUNTS
        }
        result = {
            'inventory': starter_inventory(), 'users': users, 'activity_log': [],
            'demo_password_version': DEMO_PASSWORD_VERSION,
            'starter_inventory_version': STARTER_INVENTORY_VERSION,
        }
        write_data(result)
        print('Demo accounts initialized. Passwords are listed in DEMO_ACCOUNTS at the top of this Python file.')
        return result
    try:
        with DATA_FILE.open('r', encoding='utf-8') as f:
            result = json.load(f)
        if not isinstance(result, dict) or not all(isinstance(result.get(k), t) for k, t in
            [('inventory', list), ('users', dict), ('activity_log', list)]):
            raise ValueError('Invalid data structure')
    except (OSError, ValueError) as exc:
        raise SystemExit(f'Unable to load {DATA_FILE.name}: {exc}. Restore a backup; do not delete the file.')

    old_items = result['inventory']
    try:
        result['inventory'] = normalize_inventory(old_items)
    except (ValueError, TypeError, OverflowError) as exc:
        raise SystemExit(f'Inventory data could not be migrated: {exc}. Your JSON file was not changed.')
    needs_migration = result['inventory'] != old_items
    
    replace_initial_inventory = result.get('starter_inventory_version', 0) < STARTER_INVENTORY_VERSION
    if replace_initial_inventory:
        result['inventory'] = starter_inventory()
        result['starter_inventory_version'] = STARTER_INVENTORY_VERSION
        needs_migration = True
    
    if needs_migration or result.get('demo_password_version', 0) < DEMO_PASSWORD_VERSION:
        import shutil
        backup = DATA_FILE.with_name('smart_inventory_data_before_15_item_setup.json')
        if not backup.exists():
            shutil.copy2(DATA_FILE, backup)
        if result.get('demo_password_version', 0) < DEMO_PASSWORD_VERSION:
            for username, name, role, password in DEMO_ACCOUNTS:
                result['users'][username] = {
                    'name': name, 'role': role, **password_hash(password)
                }
            result['demo_password_version'] = DEMO_PASSWORD_VERSION
        write_data(result)
        print('One-time 15-item school inventory setup completed. Accounts and activity logs preserved.')
        print('Backup saved to:', backup.name)
    return result

def write_data(content):
    temp = DATA_FILE.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    temp.replace(DATA_FILE)

def save():
    write_data(data)

def log_action(username, role, action, item=None, details='', released_value=None):
    entry = {
        'date_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'username': username, 'role': role, 'action': action,
        'item_id': item['id'] if item else None,
        'item_name': item['name'] if item else None,
        'details': details
    }

    if released_value is not None:
        entry['released_value'] = round(float(released_value), 2)
    data['activity_log'].append(entry)
    save()

def heading(title):
    print('\n' + '=' * 60)
    print(title.center(60))
    print('=' * 60)

def text(prompt):
    while True:
        answer = input(prompt).strip()
        if answer:
            return answer
        print('This field cannot be blank.')

def number(prompt, minimum=0):
    while True:
        try:
            result = int(input(prompt).strip())
            if result >= minimum:
                return result
        except ValueError:
            pass
        print(f'Enter a whole number of at least {minimum}.')

def money(prompt):
    while True:
        try:
            result = float(input(prompt).strip())
            if 0 <= result < float('inf'):
                return round(result, 2)
        except ValueError:
            pass
        print('Enter a valid non-negative price.')

def secret(prompt):
    return input(prompt)

def find_record(item_id):
    return next((i for i in data['inventory'] if i['id'] == item_id), None)

def show_items(items):
    if not items:
        print('No items found.')
        return

    headers = ['ID', 'Item Name', 'Category', 'Qty', 'Unit Price', 'Reorder', 'Total Value']
    rows = [[str(i['id']), i['name'], i['category'], str(i['quantity']),
             f"{i['unit_price']:,.2f}", str(i['reorder_level']),
             f"{i['quantity'] * i['unit_price']:,.2f}"] for i in items]
    widths = [5, 20, 20, 7, 12, 9, 15]
    print('-' * (sum(widths) + 3 * (len(headers) - 1)))
    fmt = ' | '.join('{:<%d}' % w for w in widths)
    print(fmt.format(*headers))
    print('-' * (sum(widths) + 3 * (len(headers) - 1)))
    for row in rows:

        display = [value if len(value) <= widths[c] else value[:widths[c]-3] + '...'
                   for c, value in enumerate(row)]
        print(fmt.format(*display))
    print('-' * (sum(widths) + 3 * (len(headers) - 1)))
    print('Unit Price and Total Value are in PHP.')



def find_item():
    heading('FIND ITEM BY ID')
    item = find_record(number('Enter Item ID: ', 1))
    show_items([item] if item else [])

def add_item(user):
    heading('ADD NEW ITEM')
    item_id = number('Item ID: ', 1)
    if find_record(item_id):
        print('That Item ID already exists.')
        return
    name = text('Item Name: ')
    existing = next((i for i in data['inventory']
                     if i['name'].casefold() == name.casefold()), None)
    if existing:
        print(f"Item already added! {existing['name']} (ID: {existing['id']}).")
        print('Use Add Stock / Deduct Stock to change the quantity.')
        return
    item = {'id': item_id, 'name': name,
            'category': text('Category: '), 'quantity': number('Quantity: '),
            'unit_price': money('Unit Price: '),
            'reorder_level': number('Reorder Level: ')}
    data['inventory'].append(item)
    log_action(user, 'Administrator', 'ADD ITEM', item,
               f"Initial quantity: {item['quantity']}; price: PHP {item['unit_price']:.2f}; reorder: {item['reorder_level']}")
    print('Item added successfully.')

def view_inventory():
    heading('VIEW ALL INVENTORY')
    show_items(data['inventory'])

def search_item():
    heading('SEARCH ITEM BY NAME OR CATEGORY')
    query = text('Enter Item Name or Category: ').casefold()
    matches = [i for i in data['inventory'] if query in i['name'].casefold() or query in i['category'].casefold()]
    show_items(matches)

def update_item(user):
    heading('UPDATE ITEM')
    item = find_record(number('Enter Item ID: ', 1))
    if not item:
        print('Item not found.')
        return
    show_items([item])
    fields = [('name', 'Item Name'), ('category', 'Category'), ('quantity', 'Quantity'),
              ('unit_price', 'Unit Price'), ('reorder_level', 'Reorder Level')]
    for n, (_, label) in enumerate(fields, 1):
        print(f'{n}. {label}')
    print('6. Cancel')
    choice = number('Choose field to update: ', 1)
    if choice == 6:
        return
    if choice not in range(1, 6):
        print('Invalid choice.')
        return
    key, label = fields[choice - 1]
    previous = item[key]
    if key in ('name', 'category'):
        updated = text(f'New {label}: ')
    elif key == 'unit_price':
        updated = money('New Unit Price: ')
    else:
        updated = number(f'New {label}: ')
    if key == 'name':
        existing = next((i for i in data['inventory']
                         if i['id'] != item['id'] and i['name'].casefold() == updated.casefold()), None)
        if existing:
            print(f"Item already added! Name is used by ID {existing['id']}.")
            return
    if updated == previous:
        print('No change made.')
        return
    item[key] = updated
    log_action(user, 'Administrator', 'UPDATE ITEM', item, f'{label}: {previous} -> {updated}')
    print('Item updated successfully.')

def delete_item(user):
    heading('DELETE ITEM')
    item = find_record(number('Enter Item ID: ', 1))
    if not item:
        print('Item not found.')
        return
    show_items([item])
    if input('Confirm deletion? Type YES to delete: ').strip() != 'YES':
        print('Deletion cancelled.')
        return
    details = (f"Deleted record: category={item['category']}; quantity={item['quantity']}; "
               f"unit_price={item['unit_price']}; reorder_level={item['reorder_level']}")
    data['inventory'].remove(item)
    log_action(user, 'Administrator', 'DELETE ITEM', item, details)
    print('Item deleted successfully.')

def show_stock_selection_items():
    heading('ALL INVENTORY ITEMS')
    items = data['inventory']
    if not items:
        print('No inventory items available.')
        return
    headers = ['ID', 'Item Name', 'Category', 'Available Qty']
    rows = [[str(i['id']), i['name'], i['category'], str(i['quantity'])] for i in items]
    widths = [max(len(headers[c]), *(len(row[c]) for row in rows)) for c in range(len(headers))]
    fmt = ' | '.join('{:<%d}' % width for width in widths)
    print(fmt.format(*headers))
    print('-' * (sum(widths) + 3 * (len(headers) - 1)))
    for row in rows:
        print(fmt.format(*row))


def stock_management(user, role):
    while True:
        heading('STOCK MANAGEMENT MENU')
        print('1. Add Stock')
        print('2. Deduct Stock')
        print('3. Back to Main Menu')
        choice = input('Enter your choice: ').strip()
        if choice == '3':
            return
        if choice not in ('1', '2'):
            print('Invalid choice.')
            continue
        show_stock_selection_items()
        if not data['inventory']:
            continue
        item_id = number('Enter Item ID (0 to cancel): ', 0)
        if item_id == 0:
            print('Stock transaction cancelled.')
            continue
        item = find_record(item_id)
        if not item:
            print('Item not found. Please choose an ID from the table.')
            continue
        print(f"Item: {item['name']} | Current Stock: {item['quantity']}")
        qty = number('Quantity to ' + ('add' if choice == '1' else 'deduct') + ': ', 1)
        if choice == '2' and qty > item['quantity']:
            print('Cannot deduct more than the available stock.')
            continue
        before = item['quantity']
        unit_price_at_release = item['unit_price']
        item['quantity'] += qty if choice == '1' else -qty
        action = 'ADD STOCK' if choice == '1' else 'DEDUCT STOCK'
        released_value = qty * unit_price_at_release if choice == '2' else None
        details = f'Quantity: {before} -> {item["quantity"]} (change: {qty})'
        if released_value is not None:
            details += f'; released value: PHP {released_value:,.2f}'
        log_action(user, role, action, item, details, released_value=released_value)
        print(f'{action} successful! Updated Stock: {item["quantity"]}')

def low_stock_report():
    heading('LOW STOCK REPORT')
    low = [i for i in data['inventory'] if i['quantity'] <= i['reorder_level']]
    show_items(low)
    print('Rule: Quantity <= Reorder Level')

def inventory_summary():
    heading('INVENTORY SUMMARY')
    now = datetime.now()
    today = now.date()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)             # Sunday
    month_start = today.replace(day=1)
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    month_end = next_month - timedelta(days=1)
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)

    print(f'Date: {now.strftime("%B %d, %Y")}')
    print(f'Time: {now.strftime("%I:%M:%S %p")}')
    items = data['inventory']
    print('\n' + 'INVENTORY OVERVIEW'.center(60))
    print(f'Total Item Records       : {len(items)}')
    print(f'Total Stock Quantity     : {sum(i["quantity"] for i in items)}')
    print(f'Total Inventory Value    : PHP {sum(i["quantity"] * i["unit_price"] for i in items):,.2f}')

    released = []
    for entry in data['activity_log']:
        if entry.get('action') != 'DEDUCT STOCK' or 'released_value' not in entry:
            continue
        try:
            event_date = datetime.strptime(entry['date_time'], '%Y-%m-%d %H:%M:%S').date()
            value = float(entry['released_value'])
        except (ValueError, TypeError, KeyError):
            continue
        released.append((event_date, value))

    def total_between(start, end):
        return sum(value for event_date, value in released if start <= event_date <= end)

    print('\n' + '-' * 60)
    print('STOCK RELEASED VALUE'.center(60))
    print(f'Weekly  ({week_start:%b %d} - {week_end:%b %d, %Y}) : PHP {total_between(week_start, week_end):,.2f}')
    print(f'Monthly ({month_start:%b %d} - {month_end:%b %d, %Y}) : PHP {total_between(month_start, month_end):,.2f}')
    print(f'Yearly  ({year_start:%b %d} - {year_end:%b %d, %Y}) : PHP {total_between(year_start, year_end):,.2f}')

    low_count = sum(1 for i in items if i['quantity'] <= i['reorder_level'])
    out_count = sum(1 for i in items if i['quantity'] == 0)
    print('\n' + '-' * 60)
    print('STOCK STATUS'.center(60))
    print(f'Low Stock Items           : {low_count}')
    print(f'Out of Stock Items        : {out_count}')
    print('=' * 60)
    if any(entry.get('action') == 'DEDUCT STOCK' and 'released_value' not in entry
           for entry in data['activity_log']):
        print('Note: Older stock deductions without saved released values are not included in period totals.')


def activity_logs():
    heading('VIEW ACTIVITY LOGS')
    if not data['activity_log']:
        print('No activity recorded yet.')
        return
    headers = ['No.', 'Date & Time', 'Username', 'Role', 'Action', 'Item', 'Details']
    rows = []
    for n, entry in enumerate(data['activity_log'], 1):
        item = '-'
        if entry.get('item_id') is not None:
            item = f"{entry.get('item_name') or 'Unknown'} (ID: {entry['item_id']})"
        details = entry.get('details') or '-'
        if entry.get('released_value') is not None and 'released value:' not in details.casefold():
            details += f'; released value: PHP {entry["released_value"]:,.2f}'
        rows.append([
            str(n), entry.get('date_time', '-'), entry.get('username', '-'),
            entry.get('role', '-'), entry.get('action', '-'), item, details
        ])
    
    max_widths = [4, 19, 22, 13, 16, 28, 64]
    widths = [min(max(len(headers[c]), *(len(row[c]) for row in rows)), max_widths[c])
              for c in range(len(headers))]
    fmt = ' | '.join('{:<%d}' % width for width in widths)
    print(fmt.format(*[headers[c][:widths[c]] for c in range(len(headers))]))
    print('-' * (sum(widths) + 3 * (len(headers) - 1)))
    for row in rows:
        display = [value if len(value) <= widths[c] else value[:widths[c] - 3] + '...'
                   for c, value in enumerate(row)]
        print(fmt.format(*display))


def product_history():
    """Administrator-only report of successful stock-in and stock-out movements."""
    while True:
        heading('PRODUCT HISTORY')
        print('1. View All History')
        print('2. View Weekly History')
        print('3. View Monthly History')
        print('4. View Yearly History')
        print('5. Back to Administrator Menu')
        choice = input('Enter your choice: ').strip()
        if choice == '5':
            return
        if choice not in ('1', '2', '3', '4'):
            print('Invalid choice. Try again.')
            continue

        now = datetime.now()
        today = now.date()
        if choice == '1':
            title = 'ALL PRODUCT HISTORY'
            start = end = None
            period_label = 'All recorded dates'
            empty_message = 'No stock transactions recorded yet.'
        elif choice == '2':
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            title = 'WEEKLY PRODUCT HISTORY'
            period_label = f'{start:%B %d} - {end:%B %d, %Y}'
            empty_message = 'No stock transactions recorded for this week.'
        elif choice == '3':
            start = today.replace(day=1)
            if today.month == 12:
                next_month = date(today.year + 1, 1, 1)
            else:
                next_month = date(today.year, today.month + 1, 1)
            end = next_month - timedelta(days=1)
            title = 'MONTHLY PRODUCT HISTORY'
            period_label = f'{start:%B %d} - {end:%B %d, %Y}'
            empty_message = 'No stock transactions recorded for this month.'
        else:
            start = date(today.year, 1, 1)
            end = date(today.year, 12, 31)
            title = 'YEARLY PRODUCT HISTORY'
            period_label = f'{start:%B %d, %Y} - {end:%B %d, %Y}'
            empty_message = 'No stock transactions recorded for this year.'

        movements = []
        for entry in data['activity_log']:
            action = entry.get('action')
            if action not in ('ADD STOCK', 'DEDUCT STOCK'):
                continue
            try:
                event_time = datetime.strptime(entry['date_time'], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError, KeyError):
                continue
            if start is not None and not (start <= event_time.date() <= end):
                continue
            details = entry.get('details', '')
            qty = None
            # Stock movement details are recorded as "Quantity: before -> after (change: n)".
            marker = 'change:'
            if marker in details:
                try:
                    qty = int(details.split(marker, 1)[1].split(')', 1)[0].strip())
                except (ValueError, IndexError):
                    qty = None
            if qty is None:
                continue
            movements.append({
                'event_time': event_time,
                'name': entry.get('item_name') or 'Unknown item',
                'stock_in': qty if action == 'ADD STOCK' else 0,
                'stock_out': qty if action == 'DEDUCT STOCK' else 0,
                'username': entry.get('username', '-'),
                'role': entry.get('role', '-'),
            })

        movements.sort(key=lambda row: row['event_time'], reverse=True)
        heading(title)
        print(f'Date: {now:%B %d, %Y}  |  Time: {now:%I:%M:%S %p}')
        print(f'Period: {period_label}')
        if not movements:
            print(empty_message)
            continue

        headers = ['Product Name', 'Date & Time', 'Stock In', 'Stock Out', 'Username', 'Role']
        rows = []
        for row in movements:
            rows.append([
                row['name'], row['event_time'].strftime('%Y-%m-%d %I:%M %p'),
                str(row['stock_in']) if row['stock_in'] else '-',
                str(row['stock_out']) if row['stock_out'] else '-',
                row['username'], row['role'],
            ])
        widths = [22, 20, 9, 10, 20, 15]
        fmt = ' | '.join('{:<%d}' % width for width in widths)
        print('-' * (sum(widths) + 3 * (len(headers) - 1)))
        print(fmt.format(*headers))
        print('-' * (sum(widths) + 3 * (len(headers) - 1)))
        for row in rows:
            display = [value if len(value) <= widths[c] else value[:widths[c] - 3] + '...'
                       for c, value in enumerate(row)]
            print(fmt.format(*display))
        print('-' * (sum(widths) + 3 * (len(headers) - 1)))
        print(f'Total Stock In : {sum(row["stock_in"] for row in movements)}')
        print(f'Total Stock Out: {sum(row["stock_out"] for row in movements)}')


def add_staff(admin_user):
    heading('ADD NEW STAFF')
    name = text('Staff Full Name: ')
    username = text('Staff Username: ').lower()
    if username in data['users']:
        print('That username already exists. Choose a different username.')
        return
    password = secret('Staff Password (at least 8 characters): ')
    if len(password) < 8:
        print('Password must have at least 8 characters.')
        return
    if password != secret('Confirm Password: '):
        print('Passwords do not match. Staff account was not created.')
        return
    data['users'][username] = {
        'name': name, 'role': 'Staff', **password_hash(password)
    }
    log_action(admin_user, 'Administrator', 'ADD NEW STAFF',
               details=f'Created Staff account: {username} ({name})')
    print('Staff account created successfully!')
    print(f'Full Name : {name}')
    print(f'Username  : {username}')
    print('Role      : Staff')


def change_password(user, role):
    heading('CHANGE PASSWORD')
    record = data['users'][user]
    if not valid_password(secret('Current Password: '), record):
        print('Incorrect current password. Password unchanged.')
        return
    new_password = secret('New Password (at least 8 characters): ')
    if len(new_password) < 8:
        print('New password must have at least 8 characters.')
        return
    if valid_password(new_password, record):
        print('New password must differ from current password.')
        return
    if new_password != secret('Confirm New Password: '):
        print('Passwords do not match.')
        return
    record.update(password_hash(new_password))
    log_action(user, role, 'CHANGE PASSWORD', details='Own password changed (password not recorded)')
    print('Password changed successfully.')

def login(role):
    heading(role.upper() + ' LOGIN')
    username = text('Username: ').lower()
    password = secret('Password: ')
    record = data['users'].get(username)
    if not record or record.get('role') != role or not valid_password(password, record):
        print('Invalid username, password, or role. Access denied.')
        log_action(username, role, 'FAILED LOGIN', details='Invalid credentials or selected role')
        return
    print(f"Welcome, {record['name']}!")
    log_action(username, role, 'LOGIN')
    user_menu(username, role)

def user_menu(username, role):
    admin = role == 'Administrator'
    while True:
        heading('ADMINISTRATOR MENU' if admin else 'STAFF MENU')
        if admin:
            options = [
                ('Find Item', find_item),
                ('Add New Item', lambda: add_item(username)),
                ('View All Inventory', view_inventory),
                ('Search Item', search_item),
                ('Update Item', lambda: update_item(username)),
                ('Delete Item', lambda: delete_item(username)),
                ('Add Stock / Deduct Stock', lambda: stock_management(username, role)),
                ('Low Stock Report', low_stock_report),
                ('Inventory Summary', inventory_summary),
                ('View Activity Logs', activity_logs),
                ('Product History', product_history),
                ('Add New Staff', lambda: add_staff(username)),
                ('Change Password', lambda: change_password(username, role)),
            ]
        else:
            options = [
                ('View All Inventory', view_inventory),
                ('Search Item', search_item),
                ('Add Stock / Deduct Stock', lambda: stock_management(username, role)),
                ('Low Stock Report', low_stock_report),
                ('Change Password', lambda: change_password(username, role)),
            ]
        for n, (label, _) in enumerate(options, 1):
            print(f'{n}. {label}')
        print(f'{len(options) + 1}. Logout')
        choice = input('Enter your choice: ').strip()
        if choice == str(len(options) + 1):
            log_action(username, role, 'LOGOUT')
            print('Logged out successfully.')
            return
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            options[int(choice) - 1][1]()
        else:
            print('Invalid choice. Try again.')

def main():
    global data
    data = load_data()
    while True:
        heading('SMART INVENTORY SYSTEM — WELCOME')
        print('1. Administrator Login\n2. Staff Login\n3. Exit')
        choice = input('Enter your choice: ').strip()
        if choice == '1':
            login('Administrator')
        elif choice == '2':
            login('Staff')
        elif choice == '3':
            print('Thank you for using Smart Inventory System!')
            return
        else:
            print('Invalid choice.')

if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nProgram closed.')
