import threading, queue, ctypes, os, sys, time, mmap, shutil, json, itertools
from colorama import init, Fore, Style
from datetime import datetime
init()

def load_config():
    config_file = "config.json"
    default_config = {
        "proxy_type": "http",
        "max_proxy_retries": 10
    }
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            for key, default_value in default_config.items():
                if key not in config:
                    config[key] = default_value
            return config
    except FileNotFoundError:
        print(f"{Fore.YELLOW}Config file '{config_file}' not found. Creating it...{Style.RESET_ALL}")
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        print(f"{Fore.GREEN}Created '{config_file}' with default settings.{Style.RESET_ALL}")
        return default_config
    except json.JSONDecodeError as e:
        print(f"{Fore.RED}Error parsing {config_file}: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Using default settings{Style.RESET_ALL}")
        return default_config
    except Exception as e:
        print(f"{Fore.RED}Error loading config: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Using default settings{Style.RESET_ALL}")
        return default_config

CONFIG = {
    "proxy_type": "http",
    "max_proxy_retries": 10
}

def init_config():
    global CONFIG
    CONFIG = load_config()
    if not CONFIG:
        print(f"{Fore.RED}Warning: CONFIG is empty, using defaults{Style.RESET_ALL}")
        CONFIG = {
            "proxy_type": "http",
            "max_proxy_retries": 10
        }
    return CONFIG

proxy_iterator = None
supported_proxy_types = ["http", "https", "socks4", "socks5"]

start_time = None
title_update_thread = None
should_update_title = True
threads_list = []
thread_restart_enabled = True

COMBOLIST_FILE = "input/combolist.txt"
VALID_OUTPUT_FILE = "output/valid.txt"
PROXIES_FILE = "input/proxies.txt"
BATCH_SIZE = 1000
MAX_QUEUE_SIZE = 5000

combo_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
file_lock = threading.Lock()
counters_lock = threading.Lock()
proxy_lock = threading.Lock()
print_lock = threading.Lock()
title_lock = threading.Lock()
threads_lock = threading.Lock()
queue_lock = threading.Lock()

total_combos = 0
target_thread_count = 1
combo_file_position = 0
combo_file_size = 0

valid_count = 0
pending_security_count = 0
locked_count = 0
recovery_count = 0
password_count = 0
not_exist_count = 0
invalid_count = 0
failed_count = 0

output_buffers = {}
buffer_sizes = {}
BUFFER_FLUSH_SIZE = 100

def check_windows_only():
    if os.name != "nt":
        print("This tool is designed for Windows only.")
        try:
            input("Press Enter to exit...")
        except (EOFError, ValueError):
            pass
        sys.exit(1)

def set_start_time():
    global start_time
    start_time = time.time()

def get_time():
    return datetime.now().strftime("%H:%M:%S")

def get_runtime():
    if start_time is None:
        return "00:00:00"
    elapsed = time.time() - start_time
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def safe_print(message):
    with print_lock:
        print(message + Style.RESET_ALL)
def vprint(thread_num, status, account):
    message = f"{Fore.LIGHTCYAN_EX}{get_time()} {Fore.WHITE}/ {Fore.LIGHTBLACK_EX}Thread-{int(thread_num):02} {Fore.WHITE}/ {Fore.GREEN}{status} {Fore.WHITE}/ {Fore.LIGHTGREEN_EX}{account}"
    safe_print(message)
    
def iprint(thread_num, status, account):
    message = f"{Fore.LIGHTCYAN_EX}{get_time()} {Fore.WHITE}/ {Fore.LIGHTBLACK_EX}Thread-{int(thread_num):02} {Fore.WHITE}/ {Fore.RED}{status} {Fore.WHITE}/ {Fore.LIGHTBLACK_EX}{account}"
    safe_print(message)
    
def oprint(thread_num, status, account):
    message = f"{Fore.LIGHTCYAN_EX}{get_time()} {Fore.WHITE}/ {Fore.LIGHTBLACK_EX}Thread-{int(thread_num):02} {Fore.WHITE}/ {Fore.YELLOW}{status} {Fore.WHITE}/ {Fore.LIGHTBLACK_EX}{account}"
    safe_print(message)
    
def eprint(text):
    message = f"{Fore.LIGHTCYAN_EX}{get_time()} {Fore.WHITE}/ {Fore.RED}ERROR {Fore.WHITE}/ {Fore.LIGHTRED_EX}{text}"
    safe_print(message)

def set_console_title(title):
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except:
            pass

def get_active_worker_threads():
    with threads_lock:
        return sum(1 for t in threads_list if t.is_alive())

def update_title():
    with title_lock:
        with counters_lock:
            checked = (valid_count + pending_security_count + locked_count + 
                      recovery_count + password_count + not_exist_count + 
                      invalid_count + failed_count)
            remaining = total_combos - checked
            total_valid = valid_count + pending_security_count
            total_invalid = (locked_count + recovery_count + password_count + 
                            not_exist_count + invalid_count)
        
        runtime = get_runtime()
        active_threads = get_active_worker_threads()
        
        set_console_title(f"Outlook Checker By: t.me/occursive | Runtime: {runtime} | Threads: {active_threads}/{target_thread_count} | Checked: {checked:,}/{total_combos:,} | Valid: {total_valid:,} | Invalid: {total_invalid:,} | Failed: {failed_count:,} | Remaining: {remaining:,}")

def title_updater():
    while should_update_title:
        update_title()
        time.sleep(1)

def ensure_output_folder():
    folders = [
        "output",
        "output/others"
    ]
    for folder in folders:
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
            except Exception as e:
                eprint(f"Could not create folder '{folder}': {e}")

def count_lines_fast(filename):
    try:
        with open(filename, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                return mm.count(b'\n')
    except:
        count = 0
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            for _ in f:
                count += 1
        return count

def read_batch(filename, current_position, batch_size=BATCH_SIZE):
    combos = []
    invalid_count = 0
    file_size = os.path.getsize(filename)
    
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(current_position)
            
            for _ in range(batch_size):
                line = f.readline()
                if not line:
                    break
                
                combo = line.strip()
                if combo and ':' in combo:
                    combos.append(combo)
                elif combo:
                    invalid_count += 1
            
            new_position = f.tell()
            
    except Exception as e:
        eprint(f"Error reading batch: {e}")
        return [], 0, current_position, True
        
    return combos, invalid_count, new_position, new_position >= file_size

def preprocess_combo_file(filename):
    backup_filename = filename + ".backup"
    temp_filename = filename + ".temp"
    
    if os.path.exists(backup_filename):
        os.remove(backup_filename)
    
    safe_print(f"{Fore.LIGHTCYAN_EX}Processing combo list...{Style.RESET_ALL}")
    
    if not os.path.exists(filename):
        safe_print(f"{Fore.YELLOW}Combo file '{filename}' not found. Creating it...")
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                f.write("")
            safe_print(f"{Fore.GREEN}Created '{filename}'.")
            eprint("Please add at least one combo in the following format: 'email:password'.")
            return False, 0, 0, 0
        except Exception as e:
            eprint(f"Error creating combo file: {e}")
            return False, 0, 0, 0
    
    try:
        shutil.copy2(filename, backup_filename)
        seen_combos = set()
        valid_combos = []
        duplicate_count = 0
        invalid_count = 0
        total_lines = 0
        
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                total_lines += 1
                combo = line.strip()
                
                if not combo:
                    continue
                if ':' not in combo:
                    invalid_count += 1
                    continue
                combo_lower = combo.lower()
                if combo_lower in seen_combos:
                    duplicate_count += 1
                else:
                    seen_combos.add(combo_lower)
                    valid_combos.append(combo)
        
        with open(temp_filename, 'w', encoding='utf-8') as f:
            for combo in valid_combos:
                f.write(combo + '\n')
    
        os.replace(temp_filename, filename)
        
        if os.path.exists(backup_filename):
            os.remove(backup_filename)
        
        return True, len(valid_combos), duplicate_count, invalid_count
        
    except Exception as e:
        eprint(f"Error during preprocessing: {e}")
        if os.path.exists(backup_filename):
            try:
                os.replace(backup_filename, filename)
            except:
                pass
        return False, 0, 0, 0

def load_combos_optimized(filename):
    global total_combos, combo_file_size
    
    if not os.path.exists(filename):
        eprint(f"Combo file '{filename}' not found.")
        return False
    
    try:
        total_combos = count_lines_fast(filename)
        combo_file_size = os.path.getsize(filename)
        
        if total_combos == 0:
            eprint(f"Combolist is empty. (File location: '{filename}')")
            eprint("Please add at least one combo in the following format: 'email:password'.")
            return False
            
        return True
        
    except Exception as e:
        eprint(f"Failed to analyze combo file: {e}")
        return False

def load_proxies(filename):
    if not os.path.exists(filename):
        safe_print(f"{Fore.YELLOW}Proxy file '{filename}' not found. Creating it...")
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                f.write("username:password@host:port\n")
            safe_print(f"{Fore.GREEN}Created '{filename}' with example format.")
            eprint("Please add at least one proxy in the following format: 'username:password@host:port'.")
            return []
        except Exception as e:
            eprint(f"Error creating proxy file: {e}")
            return []

    try:
        with open(filename, "r", encoding="utf-8") as f:
            proxies = [line.strip() for line in f if line.strip()]
    except Exception as e:
        eprint(f"Error reading proxies file: {e}")
        return []

    if len(proxies) == 1 and proxies[0] == "username:password@host:port":
        eprint(f"Proxy list contains only the example format. (File location: '{filename}')")
        eprint("Please add your actual proxies to the file.")
        return []

    if not proxies:
        eprint(f"Proxy list is empty. (File location: '{filename}')")
        eprint("Please add at least one proxy in the following format: 'username:password@host:port'.")
        return []

    return proxies

def update_counter(reason):
    global valid_count, pending_security_count, locked_count
    global recovery_count, password_count, not_exist_count
    global invalid_count, failed_count
    
    with counters_lock:
        if reason == "valid":
            valid_count += 1
        elif reason == "pending_security":
            pending_security_count += 1
        elif reason == "locked":
            locked_count += 1
        elif reason == "recovery":
            recovery_count += 1
        elif reason == "password":
            password_count += 1
        elif reason == "not_exist":
            not_exist_count += 1
        elif reason == "invalid":
            invalid_count += 1
        elif reason == "failed":
            failed_count += 1

def write_to_file_buffered(file_path, account):
    global output_buffers, buffer_sizes
    
    with file_lock:
        if file_path not in output_buffers:
            output_buffers[file_path] = []
            buffer_sizes[file_path] = 0
        
        output_buffers[file_path].append(account)
        buffer_sizes[file_path] += 1
        
        if buffer_sizes[file_path] >= BUFFER_FLUSH_SIZE:
            flush_buffer(file_path)

def flush_buffer(file_path):
    global output_buffers, buffer_sizes
    
    if file_path in output_buffers and output_buffers[file_path]:
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            
            with open(file_path, "a", encoding="utf-8") as f:
                for account in output_buffers[file_path]:
                    f.write(account + "\n")
            
            output_buffers[file_path] = []
            buffer_sizes[file_path] = 0
            
        except Exception as e:
            eprint(f"Failed to flush buffer to {file_path}: {e}")

def flush_all_buffers():
    with file_lock:
        for file_path in list(output_buffers.keys()):
            if buffer_sizes.get(file_path, 0) > 0:
                flush_buffer(file_path)

def combo_feeder():
    global combo_file_position, thread_restart_enabled, combo_queue
    total_invalid = 0
    
    while thread_restart_enabled:
        try:
            if combo_queue.qsize() < MAX_QUEUE_SIZE // 2:
                combos, invalid_count, combo_file_position, is_done = read_batch(
                    COMBOLIST_FILE, combo_file_position, BATCH_SIZE
                )
                total_invalid += invalid_count
                
                for combo in combos:
                    if not thread_restart_enabled:
                        break
                    try:
                        combo_queue.put(combo, timeout=1)
                    except queue.Full:
                        time.sleep(0.1)
                        break
                if is_done:
                    break
            else:
                time.sleep(0.1)
                 
        except Exception as e:
            eprint(f"Error in combo feeder: {e}")
            time.sleep(1)

def cleanup_dead_threads():
    with threads_lock:
        global threads_list
        threads_list = [t for t in threads_list if t.is_alive()]

def start_worker_thread(thread_id, checker_func):
    thread = threading.Thread(target=checker_func, args=(thread_id,), name=f"Worker-{thread_id}")
    thread.daemon = True
    thread.start()
    with threads_lock:
        threads_list.append(thread)
    return thread

def thread_monitor(checker_func):
    global thread_restart_enabled, combo_queue, combo_file_position, combo_file_size, target_thread_count
    thread_counter = 1
    last_flush = time.time()
    
    while thread_restart_enabled:
        cleanup_dead_threads()
        active_count = get_active_worker_threads()
        
        if active_count < target_thread_count and (not combo_queue.empty() or 
           combo_file_position < combo_file_size):
            needed_threads = target_thread_count - active_count
            for _ in range(needed_threads):
                start_worker_thread(thread_counter, checker_func)
                thread_counter += 1
                time.sleep(0.05)
        
        if time.time() - last_flush > 10:
            flush_all_buffers()
            last_flush = time.time()
        
        if combo_queue.empty() and combo_file_position >= combo_file_size and active_count == 0:
            break
            
        time.sleep(1)

def input_thread_count():
    global target_thread_count
    while True:
        try:
            thread_count = input(f"{Fore.LIGHTBLUE_EX}  > Enter number of threads (1-50): {Style.RESET_ALL}")
            if thread_count.isdigit():
                thread_count = int(thread_count)
                if 1 <= thread_count <= 50:
                    target_thread_count = thread_count
                    os.system('cls')
                    return thread_count
                else:
                    eprint("Please enter a number between 1 and 50.")
            else:
                eprint("Invalid input. Only numbers are allowed.")
        except (EOFError, KeyboardInterrupt):
            safe_print(f"\n{Fore.RED}Program interrupted by user.")
            return None

def print_analysis_report():
    end_time = time.time()
    total_runtime = end_time - start_time if start_time else 0
    
    flush_all_buffers()
    
    with counters_lock:
        total_checked = (valid_count + pending_security_count + locked_count + 
                        recovery_count + password_count + not_exist_count + 
                        invalid_count + failed_count)
        total_valid = valid_count + pending_security_count
        total_invalid = (locked_count + recovery_count + password_count + 
                        not_exist_count + invalid_count)
        
    avg_speed = total_checked / total_runtime if total_runtime > 0 else 0
    success_rate = (total_valid / total_checked * 100) if total_checked > 0 else 0

    print("\n")
    print(f"{Fore.WHITE}=" * 80)
    print()
    print(f"{Fore.RED}                 🎯 FINAL SUMMARY - OUTLOOK CHECKER RESULTS 🎯{Style.RESET_ALL}")
    print()
    print(f"{Fore.WHITE}=" * 80)
    print()
    print(f"{Fore.LIGHTBLUE_EX}⏱️ TIMING INFORMATION{Style.RESET_ALL}")
    print(f"   Total duration:      {Fore.YELLOW}{get_runtime()}{Style.RESET_ALL}")
    print(f"   Average speed:       {Fore.GREEN}{avg_speed:.2f} accounts/second{Style.RESET_ALL}")
    print()
    print(f"{Fore.LIGHTMAGENTA_EX}📊 OVERALL STATISTICS{Style.RESET_ALL}")
    print(f"   Total loaded:        {Fore.WHITE}{total_combos:,}{Style.RESET_ALL}")
    print(f"   Total checked:       {Fore.WHITE}{total_checked:,}{Style.RESET_ALL}")
    print(f"   Success rate:        {Fore.GREEN}{success_rate:.2f}%{Style.RESET_ALL}")
    print()
    print(f"{Fore.GREEN}✅ VALID ACCOUNTS{Style.RESET_ALL}")
    print(f"   ├─ Valid:             {Fore.GREEN}{valid_count:,}{Style.RESET_ALL}")
    print(f"   ├─ Pending Security:  {Fore.GREEN}{pending_security_count:,}{Style.RESET_ALL}")
    print(f"   └── Total Valid:      {Fore.LIGHTGREEN_EX}{total_valid:,}{Style.RESET_ALL}")
    print()
    print(f"{Fore.RED}❌ INVALID & OTHER RESULTS{Style.RESET_ALL}")
    print(f"   ├─ Locked:            {Fore.YELLOW}{locked_count:,}{Style.RESET_ALL}")
    print(f"   ├─ Recovery needed:   {Fore.YELLOW}{recovery_count:,}{Style.RESET_ALL}")
    print(f"   ├─ Wrong password:    {Fore.RED}{password_count:,}{Style.RESET_ALL}")
    print(f"   ├─ Account not exist: {Fore.RED}{not_exist_count:,}{Style.RESET_ALL}")
    print(f"   ├─ Invalid format:    {Fore.RED}{invalid_count:,}{Style.RESET_ALL}")
    print(f"   ├─ Failed checks:     {Fore.RED}{failed_count:,}{Style.RESET_ALL}")
    print(f"   └── Total invalid:    {Fore.LIGHTRED_EX}{total_invalid:,}{Style.RESET_ALL}")

def init_proxy_iterator(proxy_list, proxy_type):
    global proxy_iterator
    
    if proxy_type not in supported_proxy_types:
        eprint(f"Unsupported proxy type: {proxy_type}.")
        eprint(f"Supported types: {', '.join(supported_proxy_types)}")
        return False
    
    if not proxy_list:
        eprint("No proxies provided.")
        return False
    
    formatted_proxies = []
    for proxy in proxy_list:
        proxy = proxy.strip()
        if proxy:
            if proxy_type in ["http", "https"]:
                formatted_proxy = f"{proxy_type}://{proxy}"
            else:
                formatted_proxy = f"{proxy_type}://{proxy}"
            formatted_proxies.append(formatted_proxy)
    
    if formatted_proxies:
        proxy_iterator = itertools.cycle(formatted_proxies)
        return True
    else:
        eprint("No valid proxies found after formatting.")
        return False

def get_next_proxy():
    global proxy_iterator
    
    with proxy_lock:
        if proxy_iterator is None:
            return None
        return next(proxy_iterator)

def safe_exit():
    try:
        input(f"\n{Fore.LIGHTMAGENTA_EX}Press Enter to exit...{Style.RESET_ALL}")
    except (EOFError, ValueError, KeyboardInterrupt):
        time.sleep(10)