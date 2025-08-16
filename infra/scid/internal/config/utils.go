package config

// TODO: release this as seperate go package

import (
	"errors"
	"fmt"
	"os"
	"reflect"
	"strings"
)

func subEnv(structVal any) error {
	return subEnvStruct(reflect.ValueOf(structVal).Elem())
}

func subEnvStruct(structVal reflect.Value) error {
	for i := range structVal.NumField() {
		val := structVal.Field(i)

		switch val.Kind() {
		case reflect.String:
			err := subEnvString(val)
			if err != nil {
				return err
			}
		case reflect.Pointer:
			err := subEnvPointer(val)
			if err != nil {
				return err
			}
		case reflect.Struct:
			err := subEnvStruct(val)
			if err != nil {
				return err
			}
		case reflect.Map:
			err := subEnvMap(val)
			if err != nil {
				return err
			}
		}

	}

	return nil
}

func subEnvString(stringVal reflect.Value) error {
	s := stringVal.String()

	if strings.HasPrefix(s, "%env%:") {
		envName := strings.TrimPrefix(s, "%env%:")
		envVal, ok := os.LookupEnv(envName)
		if !ok {
			return fmt.Errorf("Environment variable %v is not set", envName)
		}

		stringVal.SetString(envVal)
	} else if strings.HasPrefix(s, "%file%:") {
		fileName := strings.TrimPrefix(s, "%file%:")
		data, err := os.ReadFile(fileName)
		if err != nil {
			return err
		}

		stringVal.SetString(strings.TrimSpace(string(data)))
	}

	return nil
}

func subEnvPointer(pointerVal reflect.Value) error {
	val := pointerVal.Elem()

	switch val.Kind() {
	case reflect.String:
		err := subEnvString(val)
		if err != nil {
			return err
		}
	case reflect.Struct:
		err := subEnvStruct(val)
		if err != nil {
			return err
		}
	case reflect.Map:
		err := subEnvMap(val)
		if err != nil {
			return err
		}
	}

	return nil
}

func subEnvMap(mapVal reflect.Value) error {
	iter := mapVal.MapRange()
	for iter.Next() {
		val := iter.Value()
		switch val.Kind() {
		case reflect.String:
			err := subEnvString(val)
			if err != nil {
				return err
			}
		case reflect.Struct:
			err := subEnvStruct(val)
			if err != nil {
				return err
			}
		case reflect.Pointer:
			err := subEnvPointer(val)
			if err != nil {
				return err
			}
		}
	}

	return nil
}
