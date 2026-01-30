fn main() {
    if let Err(e) = slint_build::compile("ui/app.slint") {
        eprintln!("Slint compilation error: {}", e);
        std::process::exit(1);
    }
}
