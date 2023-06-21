# `sites` folder

Contains sites. 

## Creating sites

```bash
nrp site add <site-name> --config <custom config>
  --no-input
```

Will create a new site. You can provide your own oarepo.yaml
config for the site via the --config option (to get the format,
run the command without --config, answer all the questions
and then copy the site part of the oarepo.yaml to your own file)

Use `--no-input` to disable asking questions (and be sure to
run it with `--config`)

## Removing sites

Just remove the site directory (and be sure to stop all 
the containers at first)

