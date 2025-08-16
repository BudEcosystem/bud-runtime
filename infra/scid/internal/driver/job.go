package driver

import (
	"fmt"
	"sync"

	"sinanmohd.com/scd/internal/config"
	"sinanmohd.com/scd/internal/git"
	"sinanmohd.com/scd/internal/slack"

	"github.com/rs/zerolog/log"
)

func JobRunIfChaged(job config.JobConfig, g *git.Git) error {
	output, execErr, err := ExecIfChaged(job.WatchPaths, job.ExecLine, g)
	if err != nil {
		return err
	}

	var color string
	if job.SlackColor == "" {
		color = "#000000"
	} else {
		color = job.SlackColor
	}

	if execErr != nil {
		slack.SendMesg(g, color, job.Name, false, fmt.Sprintf("%s: %s", execErr.Error(), output))
	} else {
		slack.SendMesg(g, color, job.Name, true, "")
	}

	return nil
}

func JobRunIfChagedWrapped(job config.JobConfig, bg *git.Git, wg *sync.WaitGroup) {
	wg.Add(1)
	go func() {
		err := JobRunIfChaged(job, bg)
		if err != nil {
			log.Fatal().Err(err).Msg("Running Job")
		}

		wg.Done()
	}()
}

func JobsRunIfChaged(g *git.Git) error {
	var jobWg sync.WaitGroup
	for _, job := range config.Config.Jobs {
		JobRunIfChagedWrapped(job, g, &jobWg)
	}
	jobWg.Wait()

	return nil
}
