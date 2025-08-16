package main

import (
	"os"
	"sync"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"

	"sinanmohd.com/scid/internal/config"
	"sinanmohd.com/scid/internal/driver"
	"sinanmohd.com/scid/internal/git"
)

func scid(g *git.Git) {
	var wg sync.WaitGroup

	wg.Add(1)
	go func() {
		if config.Config.HelmChartsPath != "" {
			driver.HelmChartsUpstallIfChaged(config.Config.HelmChartsPath, g)
		}
		wg.Done()
	}()

	wg.Add(1)
	go func() {
		driver.JobsRunIfChaged(g)
		wg.Done()
	}()

	wg.Wait()
}

func main() {
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr})
	defer log.Info().Msg("See you, bye")

	err := config.Init()
	if err != nil {
		log.Fatal().Err(err).Msg("Creating config")
	}

	g, err := git.New(config.Config.RepoUrl, config.Config.Branch)
	if err != nil {
		log.Fatal().Err(err)
	}

	originalDir, err := os.Getwd()
	if err != nil {
		log.Fatal().Err(err)
	}
	err = os.Chdir(g.LocalPath)
	if err != nil {
		log.Fatal().Err(err)
	}
	defer func() {
		err = os.Chdir(originalDir)
		if err != nil {
			log.Error().Err(err)
		}
	}()

	if !g.HeadMoved() {
		log.Info().Msg("No new commits : (")
		return
	}

	log.Info().Msgf("Branch HEAD moved: %s -> %s", g.OldHash, g.NewHash)
	scid(g)
}
