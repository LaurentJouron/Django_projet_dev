# Compilation of your frontend assets

This folder manage the construction of your static assets using the Vite build tool. The current README helps you getting started with this process. Read it carefully.

## Node.js

As a prerequisite, you will need npm to install your frontend dependencies and launch the commands. Hence, building your frontend static assets using this folder requires you to install Node.js globally on your computer. You can do this by [downloading the appropriate installer](https://nodejs.org/en/download/current) for your operating system. This is the very first step of your journey.

## Installing your project frontend dependencies

The first step to build your static files is to install frontend dependencies in the current folder. The npm package management tool (installed with Node.js) has been designed exactly for this task. It will be used to install all the tools and libraries listed in your package.json and package-lock.json files. 

Execute the following command to create automatically a node_modules subfolder with all your project frontend dependencies inside:

```bash
$ npm install
```

## Developing your frontend with the Vite build tool

### Running vite for development

For development purpose, you can start the frontend development server by running the command `$ npm start` from the current directory. This command will launch the vite dev server and recompile your static assets each time a file update is detected. It will therefore block and observe your filesystem until you stop it using CTRL+C.

### Generating your production static files

To generate your static files for deployment, use the command `$ npm run build`. It will compile and optimize your assets and store them in the static folder of your django project.

## Use Django-vite in your Django project

On the django side, using the django-vite package is a valuable option. You can install it using pip (or pipenv/poetry/uv if you prefer) like this:

```bash
$ pip install django-vite
```

Once installed, add `django_vite` in the INSTALLED_APPS list of your django settings. Then, configure it using the
DJANGO_VITE variable in your settings:

```python
DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
    },
}
```

When building for production, the static files will be stored in BASE_DIR/frontend/dist. Add the path to your production STATICFILES_DIRS.


In your templates, you need to use django-vite to reference your assets:

```html
{% load django_vite %}

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page title</title>

    {% vite_hmr_client %}
    {# path of your vite assets are relative to the frontend directory #}
    {% vite_asset 'src/main.js' %}
</head>
<body>
    ...
</body>
</html>
```

In order to use the files listed in the public directory, use the `vite_asset_url` tag :

```html
{% load static %}

{# The image bellow is located in frontend/public/images/python.png #}
<img src="{% vite_asset_url 'images/python.png' %}" alt="the python logo" />
```

For more information on django-vite, feel free to read the [offical README for the project](https://github.com/MrBin99/django-vite/blob/3.1.0/README.md).

