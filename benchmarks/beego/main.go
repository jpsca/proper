// The Beego reference app for the Proper benchmarks: the same three routes as
// benchmarks/app, over the same SQLite file.
//
//	go build -o beego-bench . && PORT=8123 ./beego-bench
package main

import (
	"fmt"
	"html/template"
	"os"
	"path/filepath"
	"sort"

	"github.com/beego/beego/v2/client/orm"
	"github.com/beego/beego/v2/server/web"
	_ "github.com/mattn/go-sqlite3"
)

type Fortune struct {
	Id      int    `orm:"pk;column(id)"`
	Message string `orm:"column(message)"`
}

func (f *Fortune) TableName() string { return "fortune" }

type BenchController struct {
	web.Controller
}

func (c *BenchController) Plaintext() {
	c.Ctx.Output.Header("Content-Type", "text/plain; charset=utf-8")
	c.Ctx.WriteString("Hello, World!")
}

func (c *BenchController) Json() {
	c.Data["json"] = map[string]string{"message": "Hello, World!"}
	c.ServeJSON()
}

func (c *BenchController) Fortunes() {
	var rows []Fortune
	if _, err := orm.NewOrm().QueryTable("fortune").All(&rows); err != nil {
		c.Abort("500")
		return
	}
	rows = append(rows, Fortune{Id: 0, Message: "Additional fortune added at request time."})
	sort.Slice(rows, func(i, j int) bool { return rows[i].Message < rows[j].Message })
	c.Data["fortunes"] = rows
	c.TplName = "fortunes.tpl"
}

func main() {
	here, _ := filepath.Abs(filepath.Dir(os.Args[0]))
	dbPath := os.Getenv("FORTUNES_DB")
	if dbPath == "" {
		dbPath = filepath.Join(here, "..", "app", "fortunes.db")
	}
	orm.RegisterDriver("sqlite3", orm.DRSqlite)
	if err := orm.RegisterDataBase("default", "sqlite3", dbPath); err != nil {
		panic(err)
	}
	orm.RegisterModel(new(Fortune))

	port := 8123
	if p := os.Getenv("PORT"); p != "" {
		fmt.Sscanf(p, "%d", &port)
	}
	web.BConfig.RunMode = web.PROD
	web.BConfig.Listen.HTTPPort = port
	web.BConfig.Listen.HTTPAddr = "127.0.0.1"
	web.BConfig.Log.AccessLogs = false
	web.BConfig.WebConfig.AutoRender = true
	web.BConfig.WebConfig.ViewsPath = filepath.Join(here, "views")
	web.BConfig.WebConfig.EnableXSRF = false
	_ = template.HTMLEscapeString // html/template escapes the messages

	web.Router("/plaintext", &BenchController{}, "get:Plaintext")
	web.Router("/json", &BenchController{}, "get:Json")
	web.Router("/fortunes", &BenchController{}, "get:Fortunes")
	web.Run()
}
