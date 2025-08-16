package driver

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"sinanmohd.com/scid/internal/git"
	"sinanmohd.com/scid/internal/slack"

	"github.com/BurntSushi/toml"
	"github.com/getsops/sops/v3/decrypt"
	"github.com/go-playground/validator/v10"
	"github.com/rs/zerolog/log"
)

const SCID_HELM_CONFIG_NAME = "scid.toml"

type SCIDToml struct {
	ReleaseName       string   `toml:"release_name" validate:"required"`
	NameSpace         string   `toml:"namespace" validate:"required"`
	ChartPathOverride string   `toml:"chart_path_override"`
	ValuePaths        []string `toml:"value_paths"`
	SopsValuePaths    []string `toml:"sops_value_paths"`
}

func HelmChartUpstallIfChaged(gitChartPath string, bg *git.Git) error {
	var scidToml SCIDToml
	// TODO: potential path traversal vulnerability i dont want to
	// waste time on it. just mention it, if requirements change in the future
	_, err := toml.DecodeFile(filepath.Join(gitChartPath, SCID_HELM_CONFIG_NAME), &scidToml)
	if err != nil {
		return err
	}
	err = validator.New().Struct(scidToml)
	if err != nil {
		return err
	}

	execLine := []string{
		"helm",
		"upgrade",
		"--install",
		"--namespace", scidToml.NameSpace,
		"--create-namespace",
	}

	for _, path := range scidToml.ValuePaths {
		fullPath := filepath.Join(gitChartPath, path)
		execLine = append(execLine, "--values", fullPath)
	}

	for _, encPath := range scidToml.SopsValuePaths {
		fullEncPath := filepath.Join(gitChartPath, encPath)
		plainContent, err := decrypt.File(fullEncPath, "yaml")
		if err != nil {
			return err
		}

		plainFile, err := os.CreateTemp("", "scid-helm-sops-enc-*.yaml")
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
	if scidToml.ChartPathOverride == "" {
		finalChartPath = gitChartPath
	} else {
		finalChartPath = filepath.Join(gitChartPath, scidToml.ChartPathOverride)
	}
	execLine = append(execLine, scidToml.ReleaseName, finalChartPath)
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
			log.Fatal().Err(err).Msgf("Upstalling Helm Chart %s", filepath.Base(gitChartPath))
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

		scidTomlPath := filepath.Join(gitChartsPath, entry.Name(), SCID_HELM_CONFIG_NAME)
		_, err := os.Stat(scidTomlPath)
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
