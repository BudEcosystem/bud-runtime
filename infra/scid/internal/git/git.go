package git

import (
	"fmt"
	"os"
	"strings"

	"github.com/go-git/go-git/v6"
	"github.com/go-git/go-git/v6/plumbing"
	"lukechampine.com/blake3"
	"sinanmohd.com/scid/internal/config"
)

type Git struct {
	LocalPath        string
	repo             *git.Repository
	NewHash, OldHash *plumbing.Hash
}

func New(repoUrl, branchName string) (*Git, error) {
	sum256 := blake3.Sum256([]byte(repoUrl + branchName))
	localPath := fmt.Sprintf("%x", sum256)

	_, err := os.Stat(localPath)
	if os.IsNotExist(err) {
		repo, err := git.PlainClone(localPath, &git.CloneOptions{
			URL:           repoUrl,
			SingleBranch:  true,
			ReferenceName: plumbing.ReferenceName(branchName),
			Progress:      os.Stdout,
		})
		if err != nil {
			return nil, err
		}

		headRef, err := repo.Head()
		if err != nil {
			return nil, err
		}
		newHash := headRef.Hash()

		return &Git{
			LocalPath: localPath,
			repo:      repo,
			NewHash:   &newHash,
			OldHash:   nil,
		}, nil
	} else if err != nil {
		return nil, err
	}

	repo, err := git.PlainOpen(localPath)
	if err != nil {
		return nil, err
	}
	headRef, err := repo.Head()
	if err != nil {
		return nil, err
	}
	oldHash := headRef.Hash()

	workTree, err := repo.Worktree()
	if err != nil {
		return nil, err
	}
	err = workTree.Pull(&git.PullOptions{
		SingleBranch: true,
	})
	if err == git.NoErrAlreadyUpToDate {
		return &Git{
			LocalPath: localPath,
			repo:      repo,
			NewHash:   &oldHash,
			OldHash:   &oldHash,
		}, nil
	} else if err != nil {
		return nil, err
	}

	headRef, err = repo.Head()
	if err != nil {
		return nil, err
	}
	newHash := headRef.Hash()

	return &Git{
		LocalPath: localPath,
		repo:      repo,
		NewHash:   &newHash,
		OldHash:   &oldHash,
	}, nil
}

func (bg *Git) HeadMoved() bool {
	if config.Config.DryRun {
		return true
	}

	return *bg.NewHash != *bg.OldHash
}

func (bg *Git) PathsUpdated(prefixPaths []string) (bool, error) {
	if config.Config.DryRun {
		return true, nil
	}

	if bg.OldHash == nil {
		return true, nil
	}

	coOld, err := bg.repo.CommitObject(*bg.OldHash)
	if err != nil {
		return false, err
	}
	treeOld, err := coOld.Tree()
	if err != nil {
		return false, err
	}

	coNew, err := bg.repo.CommitObject(*bg.NewHash)
	if err != nil {
		return false, err
	}
	treeNew, err := coNew.Tree()
	if err != nil {
		return false, err
	}

	changes, err := treeOld.Diff(treeNew)
	if err != nil {
		return false, err
	}

	for _, change := range changes {
		for _, path := range prefixPaths {
			if strings.HasPrefix(change.From.Name, path) || strings.HasPrefix(change.To.Name, path) {
				return true, nil
			}
		}
	}

	return false, nil
}
