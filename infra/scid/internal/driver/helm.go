package driver

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"sinanmohd.com/scd/internal/git"
	"sinanmohd.com/scd/internal/slack"

	"github.com/BurntSushi/toml"
	"github.com/getsops/sops/v3/decrypt"
	"github.com/go-playground/validator/v10"
	"github.com/rs/zerolog/log"
)

const SCD_HELM_CONFIG_NAME = "scd.toml"

type SCDToml struct {
	ReleaseName       string   `toml:"release_name" validate:"required"`
	NameSpace         string   `toml:"namespace" validate:"required"`
	ChartPathOverride string   `toml:"chart_path_override"`
	ValuePaths        []string `toml:"value_paths"`
	SopsValuePaths    []string `toml:"sops_value_paths"`
}

func HelmChartUpstallIfChaged(gitChartPath string, bg *git.Git) error {
	var sCdToml SCDToml
	// TODO: potential path traversal vulnerability i dont want to
	// waste time on it. just mention it, if requirements change in the future
	_, err := toml.DecodeFile(filepath.Join(gitChartPath, SCD_HELM_CONFIG_NAME), &sCdToml)
	if err != nil {
		return err
	}
	err = validator.New().Struct(sCdToml)
	if err != nil {
		return err
	}

	execLine := []string{
		"helm",
		"upgrade",
		"--install",
		"--namespace", sCdToml.NameSpace,
		"--create-namespace",
	}

	for _, path := range sCdToml.ValuePaths {
		fullPath := filepath.Join(gitChartPath, path)
		execLine = append(execLine, "--values", fullPath)
	}

	for _, encPath := range sCdToml.SopsValuePaths {
		fullEncPath := filepath.Join(gitChartPath, encPath)
		plainContent, err := decrypt.File(fullEncPath, "yaml")
		if err != nil {
			return err
		}

		plainFile, err := os.CreateTemp("", "scd-helm-sops-enc-*.yaml")
		if err != nil {
			return err
		}
		defer os.Remove(plainFile.Name())

		_, err = plainFile.WriteAt(plainContent, 0)
		if err != nil {
			return err
		}
		err = plainFile.Close()
		if err != nil {
			return err
		}

		execLine = append(execLine, "--values", plainFile.Name())
	}

	var finalChartPath string
	if sCdToml.ChartPathOverride == "" {
		finalChartPath = gitChartPath
	} else {
		finalChartPath = filepath.Join(gitChartPath, sCdToml.ChartPathOverride)
	}
	execLine = append(execLine, sCdToml.ReleaseName, finalChartPath)
	changeWatchPaths := []string{
		gitChartPath,
	}

	output, execErr, err := ExecIfChaged(changeWatchPaths, execLine, bg)
	title := fmt.Sprintf("Helm Chart %s", filepath.Base(gitChartPath))
	if execErr != nil {
		slack.SendMesg(bg, "#10148c", title, false, fmt.Sprintf("%s: %s", execErr.Error(), output))
	} else {
		slack.SendMesg(bg, "#10148c", title, true, "")
	}

	return nil
}

func HelmChartUpstallIfChagedWrapped(gitChartPath string, bg *git.Git, wg *sync.WaitGroup) {
	wg.Add(1)
	go func() {
		err := HelmChartUpstallIfChaged(gitChartPath, bg)
		if err != nil {
			log.Fatal().Err(err).Msg("Setting up Helm Chart")
		}

		wg.Done()
	}()
}

func HelmChartsUpstallIfChaged(gitChartsPath string, bg *git.Git) error {
	entries, err := os.ReadDir(gitChartsPath)
	if err != nil {
		return err
	}

	var helmWg sync.WaitGroup
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}

		sCdTomlPath := filepath.Join(gitChartsPath, entry.Name(), SCD_HELM_CONFIG_NAME)
		_, err := os.Stat(sCdTomlPath)
		if os.IsNotExist(err) {
			continue
		} else if err != nil {
			return err
		}

		HelmChartUpstallIfChagedWrapped(filepath.Join(gitChartsPath, entry.Name()), bg, &helmWg)
	}
	helmWg.Wait()

	return nil
}
