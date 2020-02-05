# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='accountbank',
            options={'verbose_name': 'Bank Account', 'verbose_name_plural': 'o- Bank Accounts'},
        ),
        migrations.AlterModelOptions(
            name='accountces',
            options={'verbose_name': 'CES Account', 'verbose_name_plural': 'o- CES Accounts'},
        ),
        migrations.AlterModelOptions(
            name='accountcrypto',
            options={'verbose_name': 'Cryptocurrency Account', 'verbose_name_plural': 'o- Cryptocurrency Accounts'},
        ),
        migrations.AlterModelOptions(
            name='address',
            options={'verbose_name': 'Address', 'verbose_name_plural': 's- Addresses'},
        ),
        migrations.AlterModelOptions(
            name='address_type',
            options={'verbose_name': 'Type of Address', 'verbose_name_plural': 's-> Types of Addresses'},
        ),
        migrations.AlterModelOptions(
            name='artwork_type',
            options={'verbose_name': 'Type of Artwork', 'verbose_name_plural': 'o--> Types of Artworks'},
        ),
        migrations.AlterModelOptions(
            name='asset',
            options={'verbose_name': 'Asset', 'verbose_name_plural': 'o- Assets'},
        ),
        migrations.AlterModelOptions(
            name='being_type',
            options={'verbose_name': 'Type of entity', 'verbose_name_plural': 'e--> Types of entities'},
        ),
        migrations.AlterModelOptions(
            name='company',
            options={'verbose_name': 'Company', 'verbose_name_plural': 'e- Companies'},
        ),
        migrations.AlterModelOptions(
            name='company_type',
            options={'verbose_name': 'Type of Company', 'verbose_name_plural': 'e-> Types of Companies'},
        ),
        migrations.AlterModelOptions(
            name='human',
            options={'verbose_name': 'Human', 'verbose_name_plural': 'e- Humans'},
        ),
        migrations.AlterModelOptions(
            name='image',
            options={'verbose_name': 'Image', 'verbose_name_plural': 'o- Images'},
        ),
        migrations.AlterModelOptions(
            name='job',
            options={'verbose_name': 'Skill', 'verbose_name_plural': 'a- Skills'},
        ),
        migrations.AlterModelOptions(
            name='material',
            options={'verbose_name': 'Material Artwork', 'verbose_name_plural': 'o- Material Artworks'},
        ),
        migrations.AlterModelOptions(
            name='material_type',
            options={'verbose_name': 'Type of Material artwork', 'verbose_name_plural': 'o-> Types of Material artworks'},
        ),
        migrations.AlterModelOptions(
            name='nonmaterial',
            options={'verbose_name': 'Non-material Artwork', 'verbose_name_plural': 'o- Non-material Artworks'},
        ),
        migrations.AlterModelOptions(
            name='nonmaterial_type',
            options={'verbose_name': 'Type of Non-material artwork', 'verbose_name_plural': 'o-> Types of Non-material artworks'},
        ),
        migrations.AlterModelOptions(
            name='person',
            options={'verbose_name': 'Person', 'verbose_name_plural': 'e- Persons'},
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'verbose_name': 'Project', 'verbose_name_plural': 'e- Projects'},
        ),
        migrations.AlterModelOptions(
            name='project_type',
            options={'verbose_name': 'Type of Project', 'verbose_name_plural': 'e-> Types of Projects'},
        ),
        migrations.AlterModelOptions(
            name='record',
            options={'verbose_name': 'Record', 'verbose_name_plural': 'o- Records'},
        ),
        migrations.AlterModelOptions(
            name='record_type',
            options={'verbose_name': 'Type of Record', 'verbose_name_plural': 'o-> Types of Records'},
        ),
        migrations.AlterModelOptions(
            name='region',
            options={'verbose_name': 'Region', 'verbose_name_plural': 's- Regions'},
        ),
        migrations.AlterModelOptions(
            name='region_type',
            options={'verbose_name': 'Type of Region', 'verbose_name_plural': 's-> Types of Regions'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_addresses',
            options={'verbose_name': 'H_addr', 'verbose_name_plural': 'Addresses of the entity'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_companies',
            options={'verbose_name': 'H_emp', 'verbose_name_plural': 'Related companies'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_jobs',
            options={'verbose_name': 'H_job', 'verbose_name_plural': 'Skills of the entity'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_materials',
            options={'verbose_name': 'H_mat', 'verbose_name_plural': 'Material Artworks'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_nonmaterials',
            options={'verbose_name': 'H_inm', 'verbose_name_plural': 'Non-material Artworks'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_persons',
            options={'verbose_name': 'H_per', 'verbose_name_plural': 'Related persons'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_projects',
            options={'verbose_name': 'H_pro', 'verbose_name_plural': 'Related projects'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_records',
            options={'verbose_name': 'H_rec', 'verbose_name_plural': 'Related records'},
        ),
        migrations.AlterModelOptions(
            name='rel_human_regions',
            options={'verbose_name': 'H_reg', 'verbose_name_plural': 'Related regions'},
        ),
        migrations.AlterModelOptions(
            name='rel_material_addresses',
            options={'verbose_name': 'M_adr', 'verbose_name_plural': 'related Addresses'},
        ),
        migrations.AlterModelOptions(
            name='rel_material_jobs',
            options={'verbose_name': 'M_ofi', 'verbose_name_plural': 'related Arts/Jobs'},
        ),
        migrations.AlterModelOptions(
            name='rel_material_materials',
            options={'verbose_name': 'M_mat', 'verbose_name_plural': 'related Material artworks'},
        ),
        migrations.AlterModelOptions(
            name='rel_material_nonmaterials',
            options={'verbose_name': 'M_inm', 'verbose_name_plural': 'related Non-materials'},
        ),
        migrations.AlterModelOptions(
            name='rel_material_records',
            options={'verbose_name': 'M_rec', 'verbose_name_plural': 'related Records'},
        ),
        migrations.AlterModelOptions(
            name='rel_nonmaterial_addresses',
            options={'verbose_name': 'N_adr', 'verbose_name_plural': 'Related addresses'},
        ),
        migrations.AlterModelOptions(
            name='rel_nonmaterial_jobs',
            options={'verbose_name': 'N_ofi', 'verbose_name_plural': 'Related Arts/Jobs'},
        ),
        migrations.AlterModelOptions(
            name='rel_nonmaterial_nonmaterials',
            options={'verbose_name': 'N_mat', 'verbose_name_plural': 'related Non-material artworks'},
        ),
        migrations.AlterModelOptions(
            name='rel_nonmaterial_records',
            options={'verbose_name': 'N_rec', 'verbose_name_plural': 'Related records'},
        ),
        migrations.AlterModelOptions(
            name='relation',
            options={'verbose_name': 'Relation', 'verbose_name_plural': 'a- Relations'},
        ),
        migrations.AlterModelOptions(
            name='space_type',
            options={'verbose_name': 'Type of Space', 'verbose_name_plural': 's--> Types of Spaces'},
        ),
        migrations.AlterModelOptions(
            name='type',
            options={'verbose_name': 'c- Type'},
        ),
        migrations.AlterModelOptions(
            name='unit',
            options={'verbose_name': 'Unit', 'verbose_name_plural': 'o- Units'},
        ),
        migrations.AlterModelOptions(
            name='unit_type',
            options={'verbose_name': 'Type of Unit', 'verbose_name_plural': 'o-> Types of Units'},
        ),
        migrations.AlterModelOptions(
            name='unitratio',
            options={'verbose_name': 'Equivalence between Units', 'verbose_name_plural': 'o- Equivalences between Units'},
        ),
        migrations.AlterField(
            model_name='accountbank',
            name='bankcard',
            field=models.BooleanField(default=False, verbose_name='with bank Card?'),
        ),
        migrations.AlterField(
            model_name='accountbank',
            name='code',
            field=models.CharField(max_length=11, null=True, verbose_name='SWIFT/BIC Code', blank=True),
        ),
        migrations.AlterField(
            model_name='accountbank',
            name='company',
            field=models.ForeignKey(verbose_name='Bank entity', blank=True, to='general.Company', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='accountbank',
            name='human',
            field=models.ForeignKey(related_name='accountsBank', verbose_name='Owner human entity', to='general.Human', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='accountbank',
            name='number',
            field=models.CharField(max_length=34, null=True, verbose_name='IBAN Account number', blank=True),
        ),
        migrations.AlterField(
            model_name='accountbank',
            name='unit',
            field=models.ForeignKey(verbose_name='Unit (currency)', blank=True, to='general.Unit', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='accountces',
            name='code',
            field=models.CharField(max_length=10, null=True, verbose_name='Network code', blank=True),
        ),
        migrations.AlterField(
            model_name='accountces',
            name='entity',
            field=models.ForeignKey(verbose_name='Network of the account', to='general.Project', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='accountces',
            name='human',
            field=models.ForeignKey(related_name='accountsCes', verbose_name='Owner human entity', to='general.Human', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='accountces',
            name='number',
            field=models.CharField(max_length=4, null=True, verbose_name='Account number', blank=True),
        ),
        migrations.AlterField(
            model_name='accountces',
            name='unit',
            field=models.ForeignKey(verbose_name='Unit (currency)', to='general.Unit', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='accountcrypto',
            name='human',
            field=models.ForeignKey(related_name='accountsCrypto', verbose_name='Owner human entity', to='general.Human', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='accountcrypto',
            name='number',
            field=models.CharField(max_length=34, verbose_name='Address of the wallet', blank=True),
        ),
        migrations.AlterField(
            model_name='accountcrypto',
            name='unit',
            field=models.ForeignKey(verbose_name='Unit (currency)', to='general.Unit', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='address',
            name='address_type',
            field=mptt.fields.TreeForeignKey(verbose_name='Type of address', blank=True, to='general.Address_Type', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='address',
            name='description',
            field=models.TextField(help_text='Exact localization, indications to arrive or comments', null=True, verbose_name='Description of the Address', blank=True),
        ),
        migrations.AlterField(
            model_name='address',
            name='ic_larder',
            field=models.BooleanField(default=False, verbose_name='Is a Larder?'),
        ),
        migrations.AlterField(
            model_name='address',
            name='jobs',
            field=models.ManyToManyField(related_name='addresses', null=True, verbose_name='Related Jobs', to='general.Job', blank=True),
        ),
        migrations.AlterField(
            model_name='address',
            name='latitude',
            field=models.IntegerField(null=True, verbose_name='Latitude (geo)', blank=True),
        ),
        migrations.AlterField(
            model_name='address',
            name='longitude',
            field=models.IntegerField(null=True, verbose_name='Longitude (geo)', blank=True),
        ),
        migrations.AlterField(
            model_name='address',
            name='name',
            field=models.CharField(help_text='The name of the Space', max_length=100, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='address',
            name='p_address',
            field=models.CharField(help_text='Postal address able to receive by post', max_length=200, verbose_name='Address'),
        ),
        migrations.AlterField(
            model_name='address',
            name='postalcode',
            field=models.CharField(max_length=5, null=True, verbose_name='Postal/Zip code', blank=True),
        ),
        migrations.AlterField(
            model_name='address',
            name='region',
            field=mptt.fields.TreeForeignKey(related_name='rel_addresses', verbose_name='Region', blank=True, to='general.Region', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='address',
            name='size',
            field=models.DecimalField(decimal_places=2, max_digits=20, blank=True, help_text='Number of units (accept 2 decimals)', null=True, verbose_name='Size'),
        ),
        migrations.AlterField(
            model_name='address',
            name='size_unit',
            field=models.ForeignKey(verbose_name='Unit of measure', blank=True, to='general.Unit', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='address',
            name='town',
            field=models.CharField(help_text='Town or City', max_length=150, verbose_name='Town'),
        ),
        migrations.AlterField(
            model_name='asset',
            name='human',
            field=models.ForeignKey(verbose_name='Entity', to='general.Human', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='asset',
            name='reciprocity',
            field=models.TextField(verbose_name='Reciprocity', blank=True),
        ),
        migrations.AlterField(
            model_name='company',
            name='company_type',
            field=mptt.fields.TreeForeignKey(verbose_name='Type of company', blank=True, to='general.Company_Type', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='company',
            name='legal_name',
            field=models.CharField(max_length=200, null=True, verbose_name='Legal name', blank=True),
        ),
        migrations.AlterField(
            model_name='company',
            name='vat_number',
            field=models.CharField(max_length=20, null=True, verbose_name='VAT/CIF', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='addresses',
            field=models.ManyToManyField(to='general.Address', null=True, verbose_name='Addresses', through='general.rel_Human_Addresses', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='birth_date',
            field=models.DateField(help_text='The day of starting existence', null=True, verbose_name='Born date', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='companies',
            field=models.ManyToManyField(related_name='hum_companies', to='general.Company', through='general.rel_Human_Companies', blank=True, null=True, verbose_name='Companies'),
        ),
        migrations.AlterField(
            model_name='human',
            name='death_date',
            field=models.DateField(help_text='The day of ceasing existence', null=True, verbose_name='Die date', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='description',
            field=models.TextField(null=True, verbose_name='Entity description', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='email',
            field=models.EmailField(help_text='The main email address of the human entity', max_length=100, verbose_name='Email', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='jobs',
            field=mptt.fields.TreeManyToManyField(to='general.Job', null=True, verbose_name='Activities, Jobs, Skills', through='general.rel_Human_Jobs', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='materials',
            field=models.ManyToManyField(to='general.Material', null=True, verbose_name='Material artworks', through='general.rel_Human_Materials', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='name',
            field=models.CharField(help_text='The name of the Entity', max_length=200, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='human',
            name='nickname',
            field=models.CharField(help_text='The nickname most used of the human entity', max_length=50, verbose_name='Nickname', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='nonmaterials',
            field=models.ManyToManyField(to='general.Nonmaterial', null=True, verbose_name='Non-material artworks', through='general.rel_Human_Nonmaterials', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='persons',
            field=models.ManyToManyField(related_name='hum_persons', to='general.Person', through='general.rel_Human_Persons', blank=True, null=True, verbose_name='Persons'),
        ),
        migrations.AlterField(
            model_name='human',
            name='projects',
            field=models.ManyToManyField(related_name='hum_projects', to='general.Project', through='general.rel_Human_Projects', blank=True, null=True, verbose_name='Projects'),
        ),
        migrations.AlterField(
            model_name='human',
            name='records',
            field=models.ManyToManyField(to='general.Record', null=True, verbose_name='Records', through='general.rel_Human_Records', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='telephone_cell',
            field=models.CharField(help_text='The main telephone of the human entity', max_length=20, verbose_name='Mobile phone', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='telephone_land',
            field=models.CharField(max_length=20, verbose_name='Land phone', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='website',
            field=models.CharField(help_text='The main web url of the human entity', max_length=100, verbose_name='Web', blank=True),
        ),
        migrations.AlterField(
            model_name='image',
            name='height',
            field=models.IntegerField(null=True, verbose_name='Height', blank=True),
        ),
        migrations.AlterField(
            model_name='image',
            name='image',
            field=models.ImageField(upload_to=b'files/images', width_field=b'width', height_field=b'height', blank=True, null=True, verbose_name='Image (jpg/png)'),
        ),
        migrations.AlterField(
            model_name='image',
            name='url',
            field=models.URLField(null=True, verbose_name='Url of the image', blank=True),
        ),
        migrations.AlterField(
            model_name='image',
            name='width',
            field=models.IntegerField(null=True, verbose_name='Width', blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='clas',
            field=models.CharField(help_text="Django model or python class associated to the Job'", max_length=50, verbose_name='Class', blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='description',
            field=models.TextField(verbose_name='Description', blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='gerund',
            field=models.CharField(help_text='The verb in gerund, present', max_length=200, verbose_name='Gerund', blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='name',
            field=models.CharField(help_text='The name of the Art', unique=True, max_length=200, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='job',
            name='verb',
            field=models.CharField(help_text='The verb of the action, infinitive', max_length=200, verbose_name='Verb', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='addresses',
            field=models.ManyToManyField(to='general.Address', null=True, verbose_name='related Addresses', through='general.rel_Material_Addresses', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='description',
            field=models.TextField(null=True, verbose_name='Description', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='jobs',
            field=models.ManyToManyField(to='general.Job', null=True, verbose_name='related Arts/Jobs', through='general.rel_Material_Jobs', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='material_type',
            field=mptt.fields.TreeForeignKey(verbose_name='Type of physical artwork', blank=True, to='general.Material_Type', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='material',
            name='materials',
            field=models.ManyToManyField(to='general.Material', null=True, verbose_name='related Material artworks', through='general.rel_Material_Materials', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='name',
            field=models.CharField(max_length=200, null=True, verbose_name='Name', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='nonmaterials',
            field=models.ManyToManyField(to='general.Nonmaterial', null=True, verbose_name='related Non-materials', through='general.rel_Material_Nonmaterials', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='records',
            field=models.ManyToManyField(to='general.Record', null=True, verbose_name='related Records', through='general.rel_Material_Records', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='addresses',
            field=models.ManyToManyField(to='general.Address', null=True, verbose_name='related Addresses', through='general.rel_Nonmaterial_Addresses', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='description',
            field=models.TextField(null=True, verbose_name='Description', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='jobs',
            field=models.ManyToManyField(to='general.Job', null=True, verbose_name='related Arts/Jobs', through='general.rel_Nonmaterial_Jobs', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='name',
            field=models.CharField(max_length=200, null=True, verbose_name='Name', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='nonmaterial_type',
            field=mptt.fields.TreeForeignKey(verbose_name='Type of non-material artwork', blank=True, to='general.Nonmaterial_Type', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='nonmaterials',
            field=models.ManyToManyField(to='general.Nonmaterial', null=True, verbose_name='related Non-material artworks', through='general.rel_Nonmaterial_Nonmaterials', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='records',
            field=models.ManyToManyField(to='general.Record', null=True, verbose_name='related Records', through='general.rel_Nonmaterial_Records', blank=True),
        ),
        migrations.AlterField(
            model_name='person',
            name='email2',
            field=models.EmailField(max_length=254, verbose_name='Alternate email', blank=True),
        ),
        migrations.AlterField(
            model_name='person',
            name='id_card',
            field=models.CharField(max_length=9, verbose_name='ID/DNI/NIE', blank=True),
        ),
        migrations.AlterField(
            model_name='person',
            name='nickname2',
            field=models.CharField(max_length=50, verbose_name='Nickname in FairNetwork', blank=True),
        ),
        migrations.AlterField(
            model_name='person',
            name='surnames',
            field=models.CharField(help_text='The surnames of the Person', max_length=200, verbose_name='Surnames', blank=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='ecommerce',
            field=models.BooleanField(default=False, verbose_name='E-commerce?'),
        ),
        migrations.AlterField(
            model_name='project',
            name='email2',
            field=models.EmailField(max_length=254, verbose_name='Alternate email', blank=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='parent',
            field=mptt.fields.TreeForeignKey(related_name='subprojects', verbose_name='Parent project', blank=True, to='general.Project', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='project',
            name='project_type',
            field=mptt.fields.TreeForeignKey(verbose_name='Type of project', blank=True, to='general.Project_Type', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='project',
            name='socialweb',
            field=models.CharField(max_length=100, verbose_name='Social website', blank=True),
        ),
        migrations.AlterField(
            model_name='record',
            name='description',
            field=models.TextField(null=True, verbose_name='Description', blank=True),
        ),
        migrations.AlterField(
            model_name='record',
            name='name',
            field=models.CharField(max_length=200, null=True, verbose_name='Name', blank=True),
        ),
        migrations.AlterField(
            model_name='record',
            name='record_type',
            field=mptt.fields.TreeForeignKey(verbose_name='Type of Record', blank=True, to='general.Record_Type', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='region',
            name='description',
            field=models.TextField(null=True, verbose_name='Description of the Region', blank=True),
        ),
        migrations.AlterField(
            model_name='region',
            name='name',
            field=models.CharField(help_text='The name of the Space', max_length=100, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='region',
            name='region_type',
            field=mptt.fields.TreeForeignKey(verbose_name='Type of region', blank=True, to='general.Region_Type', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_human_addresses',
            name='address',
            field=models.ForeignKey(related_name='rel_human', verbose_name='Address', to='general.Address', help_text='Once choosed the address, save the profile to see the changes.', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_addresses',
            name='main_address',
            field=models.BooleanField(default=False, verbose_name='Main address?'),
        ),
        migrations.AlterField(
            model_name='rel_human_addresses',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_adr+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_human_companies',
            name='company',
            field=models.ForeignKey(verbose_name='related Company', to='general.Company', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_companies',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_hum+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_human_materials',
            name='material',
            field=models.ForeignKey(verbose_name='Material artwork', to='general.Material', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_materials',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_mat+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_human_nonmaterials',
            name='nonmaterial',
            field=models.ForeignKey(verbose_name='Non-material artwork', to='general.Nonmaterial', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_nonmaterials',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_non+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_human_persons',
            name='person',
            field=models.ForeignKey(related_name='rel_humans', verbose_name='Related person', to='general.Person', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_persons',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_hum+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_human_projects',
            name='project',
            field=mptt.fields.TreeForeignKey(related_name='rel_humans', verbose_name='Related project', to='general.Project', help_text='Once choosed the project, save the profile to see the changes.', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_projects',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_hum+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_human_records',
            name='record',
            field=models.ForeignKey(verbose_name='Record', to='general.Record', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_records',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_rec+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_human_regions',
            name='region',
            field=mptt.fields.TreeForeignKey(verbose_name='Region', to='general.Region', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_regions',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_reg+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_material_addresses',
            name='address',
            field=models.ForeignKey(related_name='materials', verbose_name='related Address', to='general.Address', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_material_jobs',
            name='job',
            field=models.ForeignKey(related_name='materials', verbose_name='related Arts/Jobs', to='general.Job', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_material_jobs',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='ma_job+', verbose_name='Relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_material_materials',
            name='material2',
            field=models.ForeignKey(related_name='submaterials', verbose_name='related Material artworks', to='general.Material', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_material_materials',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='ma_mat+', verbose_name='Relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_material_nonmaterials',
            name='nonmaterial',
            field=models.ForeignKey(verbose_name='related Non-material', to='general.Nonmaterial', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_material_records',
            name='record',
            field=models.ForeignKey(verbose_name='related Record', to='general.Record', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_nonmaterial_addresses',
            name='address',
            field=models.ForeignKey(verbose_name='related Address', to='general.Address', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_nonmaterial_jobs',
            name='job',
            field=models.ForeignKey(related_name='nonmaterials', verbose_name='related Arts/Jobs', to='general.Job', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_nonmaterial_jobs',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='no_job+', verbose_name='Relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_nonmaterial_nonmaterials',
            name='nonmaterial2',
            field=models.ForeignKey(related_name='subnonmaterials', verbose_name='related Non-material Artworks', to='general.Nonmaterial', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_nonmaterial_nonmaterials',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='ma_mat+', verbose_name='Relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='rel_nonmaterial_records',
            name='record',
            field=models.ForeignKey(verbose_name='related Record', to='general.Record', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='relation',
            name='clas',
            field=models.CharField(help_text='Django model or python class associated to the Relation', max_length=50, verbose_name='Class', blank=True),
        ),
        migrations.AlterField(
            model_name='relation',
            name='description',
            field=models.TextField(verbose_name='Description', blank=True),
        ),
        migrations.AlterField(
            model_name='relation',
            name='gerund',
            field=models.CharField(help_text='The verb in gerund, present', max_length=200, verbose_name='Gerund', blank=True),
        ),
        migrations.AlterField(
            model_name='relation',
            name='name',
            field=models.CharField(help_text='The name of the Art', unique=True, max_length=200, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='relation',
            name='verb',
            field=models.CharField(help_text='The verb of the action, infinitive', max_length=200, verbose_name='Verb', blank=True),
        ),
        migrations.AlterField(
            model_name='type',
            name='clas',
            field=models.CharField(help_text='Django model or python class associated to the Type', max_length=200, verbose_name='Class', blank=True),
        ),
        migrations.AlterField(
            model_name='type',
            name='description',
            field=models.TextField(verbose_name='Description', blank=True),
        ),
        migrations.AlterField(
            model_name='type',
            name='name',
            field=models.CharField(default=b'', help_text='The name of the Concept', unique=True, max_length=200, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='unit',
            name='code',
            field=models.CharField(max_length=4, verbose_name='Code or Symbol'),
        ),
        migrations.AlterField(
            model_name='unit',
            name='description',
            field=models.TextField(null=True, verbose_name='Description', blank=True),
        ),
        migrations.AlterField(
            model_name='unit',
            name='human',
            field=models.ForeignKey(verbose_name='related Entity', blank=True, to='general.Human', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='unit',
            name='name',
            field=models.CharField(max_length=200, null=True, verbose_name='Name', blank=True),
        ),
        migrations.AlterField(
            model_name='unit',
            name='region',
            field=mptt.fields.TreeForeignKey(verbose_name='related use Region', blank=True, to='general.Region', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='unit',
            name='unit_type',
            field=mptt.fields.TreeForeignKey(verbose_name='Type of Unit', blank=True, to='general.Unit_Type', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='unitratio',
            name='in_unit',
            field=models.ForeignKey(related_name='ratio_in', verbose_name='in Unit', to='general.Unit', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='unitratio',
            name='out_unit',
            field=models.ForeignKey(related_name='ratio_out', verbose_name='out Unit', to='general.Unit', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='unitratio',
            name='rate',
            field=models.DecimalField(verbose_name='Ratio multiplier', max_digits=6, decimal_places=3),
        ),
    ]
