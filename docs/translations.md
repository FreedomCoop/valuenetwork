### Generate new .po files:

From the repo folder, enter the virtual env and do:

    ./manage.py makemessages --keep-pot


Then move the newly generated .po files (or the .pot file if needed) in the `locale/en/LC_MESSAGES/` folder (forget the .mo) to a Translation Platform:

- You can translate the strings alone in a local offline tool

- You can setup your own opensource Translations Server (like Pootle) in your local machine or in a hosting server to collaborate in a team.

- You can also use an online service like Transifex or alike.


When translating please read the code lines involved to really understand the context and the intended message.
To miss this point renders the tool totally unusable for that language.
If there are other languages already in place and you know them, take a look how they translated some strings.


When you have the translated .po file of a language, say `es.po` for Spanish:

  - paste it in the destination folder `locale/es/LC_MESSAGES/`

  - move to language destination folder: `cd locale/es/LC_MESSAGES`

  - rename the old .po: `mv django.po old-es.po`

  - rename the new es.po to django.po with: `mv es.po django.po`

  - compile the new .mo with:

    - `msgfmt -v django.po`

    - or with: `./../../../manage.py compilemessages -l es`

  - remove the old: `rm django.mo`

  - rename the new: `mv messages.mo django.mo`

  - move away or delete the 'old-es.po' file...


Do the same for every language and restart the server. That's it!

---


### To define a model field to be translatable:

  - if not installed, do: `pip install django-modeltranslation`

  - check that the app `modeltranslation` is active in the settings

  - check to have constants in the settings:

    ```
    LANGUAGE_CODE = 'en'
    LANGUAGES = (
      ('en',  _('English')),
      ('es',  _('Spanish')), # set whatever needed
    )
    DEFAULT_LANGUAGE = LANGUAGE_CODE
    ACCOUNT_LANGUAGES = LANGUAGES
    MODELTRANSLATION_DEFAULT_LANGUAGE = 'en' # can be diferent
    ```

  - place a file called `translation.py` in the app folder where the `models.py` reside, with the content:

    ```
    from modeltranslation.translator import translator, TranslationOptions
    from .models import Model1, Model2 # import your translatable models
    class Model1TranslationOptions(TranslationOptions):
        fields = ('field1','field2',) # set the translatable fields of the model
    translator.register(Model1, Model1TranslationOptions)
    ```

  - create the migrations: `./manage.py makemigrations`

  - apply them: `./manage.py migrate`

  - initially the english field (fallback) is empty, so a bunch of errors will throw, populate the fields with:

    `./manage.py update_translation_fields`

  - runs again migrate to check all is ok: `./manage.py migrate`

  - to have english strings as pre-filled in say Spanish, before doing translations and avoid errors of empty strings:

    - in settings change to new default: `MODELTRANSLATION_DEFAULT_LANGUAGE = 'es'`
    - run: `./manage.py update_translation_fields`
    - change again default to english: `MODELTRANSLATION_DEFAULT_LANGUAGE = 'en'`

Now you'll see all in english, but when you change your language and edit names or descriptions, they will remain translated for that language.

