# UPower Configuration Override

The configuration in UPower.conf.d will override the primary configuration
in UPower.conf.

The primary method for overriding settings in the main UPower.conf file is by placing configuration snippets in the `/etc/UPower/UPower.conf.d/` directory.

## The format of filename

For a file to be correctly processed as an override, its filename must adhere to a strict format:

- It must start with a two-digit number between `00` and `99`.
- It must end with the `.conf` extension.
- The middle section can contain `alphanumeric characters`, `dashes`, and `underscores`.

This format is captured by the regular expression `^([0-9][0-9])-([a-zA-Z0-9-_])*\.conf$`.

- The valid examples

```text
01-upower-example.conf
02-upower-test-123.conf
03-upower-1a2b-3c4D__.conf
```

- The invalid examples

```text
0000-upower-abcd1234.conf
001-upower-@bcd.config
```

## The configuration override

UPower processes configuration files in sorted order, where settings in later files override identical settings (matching both Group and Key) from previous files, including the main UPower.conf. This hierarchy ensures that local, numerically-prefixed files in the drop-in directory (UPower.conf.d/) take precedence.

For example, consider `UPower.conf` that contains the defaults:

```text
PercentageLow=20.0
PercentageCritical=5.0
PercentageAction=2.0
```

and there is a file `UPower.conf.d/70-change-percentages.conf`
containing settings for all `Percentage*` keys:

```text
[UPower]
PercentageLow=15.0
PercentageCritical=10.0
PercentageAction=5.0
```

and another `UPower.conf.d/99-change-percentages-local.conf`
containing settings only for `PercentageAction`:

```text
[UPower]
PercentageAction=7.5
```

First the main `UPower.conf` will be processed, then
`UPower.conf.d/70-change-percentages.conf` overriding the defaults
of all percentages from the main config file with the given values,
and finally `UPower.conf.d/99-change-percentages-local.conf`
overriding once again only `PercentageAction`. The final, effective
values are:

```text
PercentageLow=15.0
PercentageCritical=10.0
PercentageAction=7.5
```

## The examples of overriding the default percentage policy values

```text
[UPower]
PercentageLow=25.0
PercentageCritical=10.0
PercentageAction=5.0
```
