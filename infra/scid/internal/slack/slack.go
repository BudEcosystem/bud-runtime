package slack

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"sinanmohd.com/scd/internal/config"
	"sinanmohd.com/scd/internal/git"
)

type Payload struct {
	Channel     string       `json:"channel"`
	Attachments []Attachment `json:"attachments"`
}

type Attachment struct {
	Color      string  `json:"color"`
	Title      string  `json:"title"`
	Text       string  `json:"text"`
	Fields     []Field `json:"fields"`
	Footer     string  `json:"footer"`
	FooterIcon string  `json:"footer_icon"`
	Timestamp  int64   `json:"ts"`
}

type Field struct {
	Title string `json:"title"`
	Value string `json:"value"`
	Short bool   `json:"short"`
}

func SendMesg(g *git.Git, color, title string, success bool, extraText string) error {
	if config.Config.Slack == nil || config.Config.DryRun {
		return nil
	}

	var text string
	if success {
		text = fmt.Sprintf("Successfully updated %s\n%s", title, extraText)
	} else {
		color = "#FF0000"
		text = fmt.Sprintf("Failed to update %s\n%s", title, extraText)
	}

	data := Payload{
		Channel: config.Config.Slack.Channel,
		Attachments: []Attachment{{
			Color:      color,
			Title:      fmt.Sprintf("%s Update", title),
			Text:       text,
			Footer:     "scd",
			FooterIcon: "https://avatars.githubusercontent.com/u/69694713?v=4&s=75",
			Timestamp:  time.Now().Unix(),

			Fields: []Field{
				{
					Title: "Old Git HEAD",
					Value: fmt.Sprint(g.OldHash),
					Short: false,
				},
				{
					Title: "New Git HEAD",
					Value: g.NewHash.String(),
					Short: false,
				},
			},
		}},
	}
	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}

	req, err := http.NewRequest(http.MethodPost, "https://slack.com/api/chat.postMessage", bytes.NewBuffer(jsonData))
	if err != nil {
		return err
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", config.Config.Slack.Token))
	req.Header.Set("Content-Type", "application/json")
	_, err = http.DefaultClient.Do(req)
	if err != nil {
		return err
	}

	return nil
}
