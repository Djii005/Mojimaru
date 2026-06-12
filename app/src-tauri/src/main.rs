// Prevents an extra Windows console window from appearing.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    mojimaru_app_lib::run()
}
