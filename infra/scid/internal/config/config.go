package config

import (
	"errors"
	"flag"
	"os"

	"github.com/BurntSushi/toml"
	"github.com/go-playground/validator/v10"
)

type SlackConfig struct {
	Channel string `toml:"channel" validate:"required"`
	Token   string `toml:"token" validate:"required"`
}

type JobConfig struct {
	Name       string   `toml:"name" validate:"required"`
	ExecLine   []string `toml:"exec_line" validate:"required"`
	WatchPaths []string `toml:"watch_paths" validate:"required"`
	SlackColor string   `toml:"slack_color" validate:"hexcolor"`
}

type SCIDonfig struct {
	Branch         string       `toml:"branch" validate:"required"`
	RepoUrl        string       `toml:"repo_url" validate:"required"`
	DryRun         bool         `toml:"dry_run"`
	HelmChartsPath string       `toml:"helm_charts_path"`
	Slack          *SlackConfig `toml:"slack"`
	Jobs           []JobConfig  `toml:"jobs" validate:"dive"`
}

var Config SCIDonfig

func Init() error {
	var configPath string
	defaultConfigPath := "/etc/scid.toml"
	if value, ok := os.LookupEnv("SCID_CONFIG"); ok {
		configPath = value
	} else {
		configPath = defaultConfigPath
	}

	_, err := os.Stat(configPath)
	if err != nil {
		if configPath == defaultConfigPath && !errors.Is(err, os.ErrNotExist) {
			return err
		} else if configPath != defaultConfigPath {
			return err
		}
	}

	if _, err := os.Stat(configPath); err == nil {
		_, err := toml.DecodeFile(configPath, &Config)
		if err != nil {
			return err
		}
	} else if !os.IsNotExist(err) {
		return err
	}

	flag.StringVar(&Config.RepoUrl, "repo", Config.RepoUrl, "Git Repo URL")
	flag.StringVar(&Config.Branch, "branch", Config.Branch, "Git Branch Name")
	flag.StringVar(&Config.HelmChartsPath, "helm-charts-path", Config.HelmChartsPath, "Path to Helm Charts")
	flag.BoolVar(&Config.DryRun, "dry-run", Config.DryRun, "Dry Run")
	flag.Parse()

	err = subEnv(&Config)
	if err != nil {
		return err
	}

	err = validator.New().Struct(Config)
	if err != nil {
		return err
	}

	return nil
}
