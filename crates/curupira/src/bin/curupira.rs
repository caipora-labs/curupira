fn main() {
    let code = curupira::run(std::env::args_os());
    std::process::exit(code);
}
