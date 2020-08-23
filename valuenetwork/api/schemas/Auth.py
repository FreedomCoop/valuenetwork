from six import with_metaclass
import datetime
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
import graphene
#from graphene import ObjectTypeMeta
#from graphene.types.mutation import MutationMeta # not working in py3 TODO
#from graphene.utils.is_base_type import is_base_type
import jwt
from .helpers import hash_password


class CreateToken(graphene.Mutation):
    class Meta:
        #abstract = True
        def __new__(cls, name, bases, attrs):
            #if not is_base_type(bases, _AuthedMutationMeta):
            #    return type.__new__(cls, name, bases, attrs)

            # store a ref to the original mutate method (not the classmethod wrapper!)
            orig_mutate = getattr(attrs['mutate'], '__func__')

            # define wrapper logic for this class
            def new_mutate(root, info, token, **args): #cls, root, info, token, **args) #args, context, info):
                print("new_mutate! ")
                # authenticate automagically before running mutation, throw exception on bad credentials
                info.context.user = _authUser(token) #args.get('token'))
                # now run the original mutation, exposing the user in the context object
                return orig_mutate(root, info, **args) #cls, root, info, **args) #args, context, info)

            # override base mutate classmethod
            attrs['mutate'] = classmethod(new_mutate)

            return self.__new__(cls, name, bases, attrs)

    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)

    token = graphene.String()

    def mutate(root, info, username, password, **args): #cls, root, info, **args): #args, context, info):
        #username = args.get('username')
        #password = args.get('password')
        user = authenticate(username=username, password=password)
        #print("auth-mutate! user:"+str(user))
        hashed_passwd = hash_password(user)
        if user is not None:
            token = jwt.encode({
                'id': user.id,
                'username': user.username,
                'password': hashed_passwd,
                'iat': datetime.datetime.now(),
            }, settings.SECRET_KEY)
            encoded = token
        else:
            raise PermissionDenied('Invalid credentials')
        return CreateToken(token=encoded)


# Auth helper, metaclass & superclass for setting up mutations which require authentication (ie. most of them)
def _authUser(token_str):
    print("_authUser! ")
    token = jwt.decode(token_str, settings.SECRET_KEY)
    user = User.objects.get_by_natural_key(token['username'])
    if token is not None and user is not None:
        if token['password'] != hash_password(user):
            raise PermissionDenied("Invalid credentials")
        return user
    raise PermissionDenied('Invalid credentials')   # purposefully generic error to guard against hack attempt info gathering

"""
class _AuthedMutationMeta(graphene.ObjectTypeMeta): #MutationMeta):
    def __new__(cls, name, bases, attrs):
        if not is_base_type(bases, _AuthedMutationMeta):
            return type.__new__(cls, name, bases, attrs)

        # store a ref to the original mutate method (not the classmethod wrapper!)
        orig_mutate = getattr(attrs['mutate'], '__func__')

        # define wrapper logic for this class
        def new_mutate(cls, root, args, context, info):
            # authenticate automagically before running mutation, throw exception on bad credentials
            context.user = _authUser(args.get('token'))
            # now run the original mutation, exposing the user in the context object
            return orig_mutate(cls, root, args, context, info)

        # override base mutate classmethod
        attrs['mutate'] = classmethod(new_mutate)

        return MutationMeta.__new__(cls, name, bases, attrs)
"""

class AuthedMutation(CreateToken): # with_metaclass(_AuthedMutationMeta, graphene.ObjectType)):
    pass

class AuthedInputMeta(type):
    def __new__(mcs, classname, bases, dictionary):
        dictionary['token'] = graphene.String(required=True)
        #print("dictionary: "+str(dictionary)) #AuthedInputMeta __new__ !!")
        return type.__new__(mcs, classname, bases, dictionary)
