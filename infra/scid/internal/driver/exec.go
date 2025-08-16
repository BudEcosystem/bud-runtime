package driver

import (
	"fmt"
	"os/exec"

	"github.com/rs/zerolog/log"

	"sinanmohd.com/scd/internal/config"
	"sinanmohd.com/scd/internal/git"
)

func ExecIfChaged(paths, execLine []string, bg *git.Git) (string, error /* exec error */, error) {
	changed, err := bg.PathsUpdated(paths)
	if err != nil {
		return "", nil, err
	}
	if changed == false {
		return "", nil, err
	}

	log.Info().Msg(fmt.Sprintf("Execing %v", execLine))

	if config.Config.DryRun {
		return "", nil, nil
	}

	output, err := exec.Command(execLine[0], execLine[1:]...).CombinedOutput()
	if err != nil {
		return string(output), err, nil
	}
	return string(output), nil, nil
}
