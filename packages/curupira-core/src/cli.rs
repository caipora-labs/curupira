//! Clap CLI surface preserving public commands and exit codes.

use std::ffi::OsString;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use clap::{CommandFactory, Parser, Subcommand};

use crate::config::{load_settings, LogLevel};
use crate::error::CurupiraError;
use crate::extensions::manager::{install_extension, uninstall_extension, ExtensionSource};
use crate::extensions::registry::{describe_installed, ExtensionRegistry};
use crate::runtime::{
    default_config_path, ensure_runtime_directories, prepare_default_config_parent,
    DispatchInstanceLock,
};
use crate::version::VERSION;

/// Exit code for Ctrl-C / KeyboardInterrupt parity with the former Python CLI.
pub const EXIT_INTERRUPTED: i32 = 130;

#[derive(Debug, Parser)]
#[command(
    name = "curupira",
    about = "Dispatch GitHub and cron automations to native coding-agent CLIs.",
    disable_help_subcommand = true
)]
struct Root {
    /// TOML configuration file (default: ~/.curupira/settings.toml)
    #[arg(long, global = true)]
    config: Option<PathBuf>,

    /// Override [settings].log_level for this process
    #[arg(long, global = true, value_parser = parse_log_level_arg)]
    log_level: Option<LogLevel>,

    /// Show the version and exit
    #[arg(long)]
    version: bool,

    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Validate configuration without calling external CLIs or writing state
    Validate,
    /// Drain currently available automation tasks, or watch continuously with --watch
    Run {
        /// Preview a task without reserving, persisting, cloning, or executing
        #[arg(long)]
        dry_run: bool,
        /// Poll all automations continuously until interrupted
        #[arg(long)]
        watch: bool,
        /// Process at most N tasks (finite drain only)
        #[arg(long, value_parser = clap::value_parser!(u32).range(1..))]
        size: Option<u32>,
    },
    /// Run the orchestrator with an interactive terminal dashboard
    Tui,
    /// Inspect and manage process-based extensions
    #[command(subcommand)]
    Plugins(PluginsCommand),
}

#[derive(Debug, Subcommand)]
enum PluginsCommand {
    /// List registered trigger types and agent providers
    List,
    /// Show details for one installed extension
    Info { name: String },
    /// Install an extension from pip: or npm: (requires confirmation unless --yes)
    Install {
        /// Source such as pip:package==1.2.3 or npm:package@1.2.3 or path:/abs/or/rel
        source: String,
        /// Skip the interactive confirmation prompt
        #[arg(long)]
        yes: bool,
    },
    /// Remove a managed extension by name
    Uninstall { name: String },
}

fn parse_log_level_arg(raw: &str) -> Result<LogLevel, String> {
    LogLevel::parse(raw)
}

fn program_name(argv0: Option<&OsString>) -> String {
    let raw = argv0
        .and_then(|s| s.to_str())
        .map(PathBuf::from)
        .and_then(|p| p.file_name().map(|n| n.to_string_lossy().into_owned()))
        .unwrap_or_else(|| "curupira".into());
    let mut name = raw;
    if let Some(stripped) = name.strip_suffix(".exe") {
        name = stripped.to_string();
    }
    let lower = name.to_ascii_lowercase();
    if lower == "curupira" || lower == "curu" {
        lower
    } else {
        "curupira".into()
    }
}

/// Parse argv and execute; returns a process exit code.
pub fn execute<I, T>(args: I) -> Result<i32, CurupiraError>
where
    I: IntoIterator<Item = T>,
    T: Into<OsString> + Clone,
{
    let args: Vec<OsString> = args.into_iter().map(Into::into).collect();
    let prog = program_name(args.first());

    let interrupted = Arc::new(AtomicBool::new(false));
    let flag = Arc::clone(&interrupted);
    let _ = ctrlc::set_handler(move || {
        flag.store(true, Ordering::SeqCst);
    });

    let root = match Root::try_parse_from(&args) {
        Ok(root) => root,
        Err(err) => {
            let mut out = if err.use_stderr() {
                Box::new(std::io::stderr()) as Box<dyn Write>
            } else {
                Box::new(std::io::stdout())
            };
            let _ = write!(out, "{err}");
            return Ok(err.exit_code());
        }
    };

    if root.version {
        println!("{prog} {VERSION}");
        return Ok(0);
    }

    let Some(command) = root.command else {
        let mut cmd = Root::command();
        let _ = cmd.print_help();
        println!();
        return Ok(2);
    };

    let config = root.config.unwrap_or_else(default_config_path);

    let result = match command {
        Command::Validate => cmd_validate(&config, root.log_level),
        Command::Run {
            dry_run,
            watch,
            size,
        } => {
            if watch && dry_run {
                eprintln!("Configuration error: --dry-run cannot be combined with --watch");
                return Ok(2);
            }
            if watch && size.is_some() {
                eprintln!("Configuration error: --size cannot be combined with --watch");
                return Ok(2);
            }
            if dry_run && size.is_some() {
                eprintln!("Configuration error: --size cannot be combined with --dry-run");
                return Ok(2);
            }
            cmd_run(&config, root.log_level, dry_run, watch, size, &interrupted)
        }
        Command::Tui => cmd_tui(&config, root.log_level, &interrupted),
        Command::Plugins(sub) => cmd_plugins(&config, sub),
    };

    if interrupted.load(Ordering::SeqCst) {
        return Ok(EXIT_INTERRUPTED);
    }

    match result {
        Ok(()) => Ok(0),
        Err(err) => {
            eprintln!("{err}");
            Ok(err.exit_code())
        }
    }
}

fn cmd_validate(config: &Path, log_level: Option<LogLevel>) -> Result<(), CurupiraError> {
    prepare_default_config_parent(config)?;
    let _settings = load_settings(config, log_level)?;
    println!("Configuration is valid: {}", config.display());
    Ok(())
}

fn cmd_run(
    config: &Path,
    log_level: Option<LogLevel>,
    dry_run: bool,
    watch: bool,
    size: Option<u32>,
    interrupted: &AtomicBool,
) -> Result<(), CurupiraError> {
    prepare_default_config_parent(config)?;
    let mut lock = None;
    if !dry_run {
        ensure_runtime_directories()?;
        let mut instance =
            DispatchInstanceLock::new(crate::runtime::dispatch_home().join("dispatch.lock"));
        instance.acquire()?;
        lock = Some(instance);
    }
    let settings = load_settings(config, log_level)?;
    let rt = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    let outcome = rt.block_on(crate::dispatch::run_command(
        &settings,
        dry_run,
        watch,
        size,
        interrupted,
    ));
    drop(lock);
    outcome
}

fn cmd_tui(
    config: &Path,
    log_level: Option<LogLevel>,
    interrupted: &AtomicBool,
) -> Result<(), CurupiraError> {
    prepare_default_config_parent(config)?;
    ensure_runtime_directories()?;
    let mut instance =
        DispatchInstanceLock::new(crate::runtime::dispatch_home().join("dispatch.lock"));
    instance.acquire()?;
    let settings = load_settings(config, log_level)?;
    let rt = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    eprintln!("TUI: running dispatch dashboard (status mode); press Ctrl+C to stop");
    let outcome = rt.block_on(crate::dispatch::run_command(
        &settings,
        false,
        true,
        None,
        interrupted,
    ));
    drop(instance);
    outcome
}

fn cmd_plugins(config: &Path, command: PluginsCommand) -> Result<(), CurupiraError> {
    ensure_runtime_directories()?;
    let registry = ExtensionRegistry::load()?;
    match command {
        PluginsCommand::List => {
            for line in describe_installed(&registry)? {
                println!("{line}");
            }
            Ok(())
        }
        PluginsCommand::Info { name } => {
            let info = registry.get(&name).ok_or_else(|| {
                CurupiraError::Plugin(format!("extension {name:?} is not installed"))
            })?;
            println!(
                "{}",
                toml::to_string_pretty(&info.manifest)
                    .map_err(|e| CurupiraError::Plugin(e.to_string()))?
            );
            Ok(())
        }
        PluginsCommand::Install { source, yes } => {
            let parsed = ExtensionSource::parse(&source)?;
            if !yes {
                eprint!("Install extension from {source}? [y/N] ");
                let mut answer = String::new();
                std::io::stdin()
                    .read_line(&mut answer)
                    .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
                if !matches!(answer.trim().to_ascii_lowercase().as_str(), "y" | "yes") {
                    return Err(CurupiraError::Message("installation cancelled".into()));
                }
            }
            let env_vars = crate::config::environment_vars_from_config(config)?;
            let installed = install_extension(&parsed, &env_vars)?;
            println!("Installed extension {}", installed.name);
            Ok(())
        }
        PluginsCommand::Uninstall { name } => {
            uninstall_extension(&name)?;
            println!("Uninstalled extension {name}");
            Ok(())
        }
    }
}
